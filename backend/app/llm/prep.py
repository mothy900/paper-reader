"""읽기 전 준비: 사전지식 카드와 데이터 뼈대 카드의 입력 구성과 결과 검증.

입력은 논문 일부(서론·결론 / Methods + 표 이미지)만 보낸다. 결과의 근거는 서버가 원문과 대조해 표시한다.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, col, select

from app.llm.context import render_block_png
from app.llm.tasks import DATA_FIELDS, PREP_CONCEPTS, PREP_DATA, Task
from app.models import Block, BlockType, Paper, Sentence
from app.storage import Storage
from app.text import normalize

METHODS_RE = re.compile(r"method|material|experiment|data|setup|procedure|training", re.IGNORECASE)
INTRO_RE = re.compile(r"introduction|background", re.IGNORECASE)
CONCLUSION_RE = re.compile(r"conclusion|summary|discussion", re.IGNORECASE)
REFERENCES_RE = re.compile(r"^(references|bibliography|literature cited)\b", re.IGNORECASE)
SUPPLEMENT_RE = re.compile(
    r"supplementar|supporting information|\b(table|fig\.?|figure)\s*S\d|data (are|is) available", re.IGNORECASE
)
MAX_METHODS_CHARS = 24_000
MAX_FALLBACK_CHARS = 40_000
MAX_SECTION_CHARS = 6_000
MAX_TABLES = 3
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class PrepInput:
    task: Task
    values: dict[str, str]
    images: list[tuple[str, bytes | None]] = field(default_factory=list)  # (표 id, PNG — 조회용이면 None)
    scope: str = ""


def _blocks(session: Session, paper_id: str) -> list[Block]:
    return list(
        session.exec(
            select(Block).where(Block.paper_id == paper_id, col(Block.hidden).is_(False)).order_by(col(Block.seq))
        )
    )


def _sentences(session: Session, paper_id: str) -> dict[str, list[Sentence]]:
    out: dict[str, list[Sentence]] = {}
    for s in session.exec(select(Sentence).where(Sentence.paper_id == paper_id).order_by(col(Sentence.idx))):
        out.setdefault(s.block_id, []).append(s)
    return out


def _top_sections(blocks: list[Block]) -> list[tuple[Block, list[Block]]]:
    """1단계 제목과 그 아래 블록들 (참고문헌 전까지)."""
    sections: list[tuple[Block, list[Block]]] = []
    for b in blocks:
        if b.type is BlockType.heading and (b.level or 1) == 1:
            if REFERENCES_RE.match(b.text.strip()):
                break
            sections.append((b, []))
        elif sections:
            sections[-1][1].append(b)
    return sections


def _body_until_references(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for b in blocks:
        if b.type is BlockType.heading and REFERENCES_RE.match(b.text.strip()):
            break
        out.append(b)
    return out


def _tagged(blocks: list[Block], sentences: dict[str, list[Sentence]], limit: int) -> str:
    """문장마다 id를 붙인 텍스트. 모델이 근거를 이 id로 가리킨다."""
    parts: list[str] = []
    size = 0
    for b in blocks:
        if b.type is BlockType.heading:
            line = f'<h id="{b.id}">{b.text}</h>'
        elif b.type in (BlockType.paragraph, BlockType.equation):
            sents = sentences.get(b.id) or []
            line = "".join(f'<s id="{b.id}:{s.idx}">{b.text[s.start : s.end]}</s>' for s in sents) or b.text
        else:
            continue
        size += len(line)
        if size > limit:
            parts.append("<truncated/>")
            break
        parts.append(line)
    return "\n".join(parts)


def prepare_data(session: Session, storage: Storage, paper: Paper, *, render: bool = True) -> PrepInput:
    """render=False면 표 이미지를 그리지 않는다 (저장된 결과 조회용, 캐시 키에는 표 id만 쓴다)."""
    blocks = _blocks(session, paper.id)
    sentences = _sentences(session, paper.id)
    matched = [(h, body) for h, body in _top_sections(blocks) if METHODS_RE.search(h.text)]
    if matched:
        scope_blocks = [b for h, body in matched for b in (h, *body)]
        scope = "섹션: " + ", ".join(h.text for h, _ in matched)
        text = _tagged(scope_blocks, sentences, MAX_METHODS_CHARS)
    else:
        scope_blocks = _body_until_references(blocks)
        scope = "Methods 섹션을 찾지 못해 본문 전체"
        text = _tagged(scope_blocks, sentences, MAX_FALLBACK_CHARS)

    tables = _pick_tables(blocks, scope_blocks)
    images = [(f"table:{t.id}", render_block_png(storage, paper, t) if render else None) for t in tables]
    captions = "\n".join(
        f"[table:{b.id}] {b.text[: _caption_len(b, sentences)]}" if b.type is BlockType.table else f"[{b.id}] {b.text}"
        for b in blocks
        if b.type in (BlockType.caption, BlockType.table)
    )
    return PrepInput(
        PREP_DATA,
        {"title": paper.title, "scope": scope, "methods": text, "captions": captions},
        images=images,
        scope=scope,
    )


def prepare_concepts(session: Session, paper: Paper) -> PrepInput:
    blocks = _blocks(session, paper.id)
    sections = _top_sections(blocks)
    outline = "\n".join(
        f'<h id="{b.id}" level="{b.level or 1}">{b.text}</h>' for b in blocks if b.type is BlockType.heading
    )
    chosen = [s for s in sections if INTRO_RE.search(s[0].text)][:1] + [
        s for s in sections if CONCLUSION_RE.search(s[0].text)
    ][-1:]
    body = "\n".join(
        f'<section id="{h.id}" title="{h.text}">{_clip(" ".join(b.text for b in part if b.type is BlockType.paragraph), MAX_SECTION_CHARS)}</section>'
        for h, part in chosen
    )
    return PrepInput(
        PREP_CONCEPTS,
        {"title": paper.title, "abstract": paper.abstract or "", "outline": outline, "sections": body},
    )


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " …"


def _caption_len(block: Block, sentences: dict[str, list[Sentence]]) -> int:
    sents = sentences.get(block.id) or []
    return sents[0].end if sents else len(block.text)


def _pick_tables(blocks: list[Block], scope: list[Block]) -> list[Block]:
    """Methods 안에 있거나 Methods에서 언급된 표 (최대 3개)."""
    tables = [b for b in blocks if b.type is BlockType.table]
    scope_ids = {b.id for b in scope}
    inside = [t for t in tables if t.id in scope_ids]
    scope_text = " ".join(b.text for b in scope)
    mentioned = [
        t
        for t in tables
        if t not in inside and (m := re.match(r"(table\s*\d+)", t.text, re.IGNORECASE))
        and re.search(rf"\b{re.escape(m.group(1))}\b", scope_text, re.IGNORECASE)
    ]
    return (inside + mentioned)[:MAX_TABLES]


# ---- 결과 검증 ----


def _loose(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", normalize(text).lower())


@dataclass
class _Ref:
    block_id: str
    text: str
    kind: str  # sentence | table | block


def _resolve(ref: str, blocks: dict[str, Block], sentences: dict[str, list[Sentence]]) -> _Ref | None:
    ref = ref.strip()
    if ref.startswith("table:"):
        b = blocks.get(ref[6:])
        return _Ref(b.id, b.text, "table") if b else None
    if ":" in ref:
        block_id, idx = ref.rsplit(":", 1)
        b = blocks.get(block_id)
        sent = next((s for s in sentences.get(block_id, []) if str(s.idx) == idx), None)
        if b and sent:
            return _Ref(b.id, b.text[sent.start : sent.end], "sentence")
        return _Ref(b.id, b.text, "block") if b else None
    b = blocks.get(ref)
    return _Ref(b.id, b.text, "block") if b else None


def _check_evidence(items: list[dict], blocks: dict[str, Block], sentences: dict[str, list[Sentence]]) -> list[dict]:
    """근거마다 실제 위치(block_id)와 확인 상태를 붙인다: verified / image(표 이미지라 자동 확인 불가) / unverified."""
    out = []
    for ev in items:
        resolved = _resolve(ev.get("ref", ""), blocks, sentences)
        quote = _loose(ev.get("quote", ""))
        if resolved is None:
            check = "unverified"
        elif resolved.kind == "table":
            check = "verified" if quote and quote in _loose(resolved.text) else "image"
        else:
            check = "verified" if quote and quote in _loose(resolved.text) else "unverified"
        out.append({**ev, "block_id": resolved.block_id if resolved else None, "check": check})
    return out


def verify_data(result: dict[str, Any], session: Session, paper_id: str) -> dict[str, Any]:
    """모델 결과에 근거 확인 표시, 숫자 대조, 보충 자료 언급을 덧붙인다. 원본 결과는 바꾸지 않는다."""
    blocks = {b.id: b for b in _blocks(session, paper_id)}
    sentences = _sentences(session, paper_id)
    paper_text = normalize(" ".join(b.text for b in blocks.values()))
    fields = {}
    for name in DATA_FIELDS:
        f = dict(result.get("fields", {}).get(name, {}))
        f["evidence"] = _check_evidence(f.get("evidence", []), blocks, sentences)
        # 논문 어디에도 없는 숫자 = 지어냈거나 계산한 값. 모델 이름(ResNet-110)이나 조건(25 °C)처럼
        # 근거 문장 밖에만 있는 숫자는 사실과 무관할 수 있어 문제 삼지 않는다.
        missing = [n for n in dict.fromkeys(_NUMBER.findall(f.get("value", ""))) if not _has_number(paper_text, n)]
        f["numbers_unverified"] = missing
        from_table = any(e["check"] == "image" for e in f["evidence"])
        if missing and f.get("status") == "stated" and not from_table:
            # 논문에 없는 숫자를 "명시"라고 할 수 없다. 표 이미지가 근거면 숫자를 자동 대조할 수 없어 내리지 않는다.
            f["status"] = "inferred"
        fields[name] = f
    warnings = [
        {**w, "evidence": _check_evidence(w.get("evidence", []), blocks, sentences)} for w in result.get("warnings", [])
    ]
    return {**result, "fields": fields, "warnings": warnings, "supplementary": supplementary_mentions(blocks)}


def _has_number(text: str, number: str) -> bool:
    """숫자 경계를 지켜 찾는다 ("110"이 "1100" 안에서 걸리지 않게)."""
    return re.search(rf"(?<![\d.]){re.escape(number)}(?![\d])", text) is not None


def verify_concepts(result: dict[str, Any], session: Session, paper_id: str) -> dict[str, Any]:
    ids = {b.id for b in _blocks(session, paper_id)}
    concepts = [
        {**c, "section_ref": c.get("section_ref") if c.get("section_ref") in ids else ""}
        for c in result.get("concepts", [])
    ]
    return {**result, "concepts": concepts}


def supplementary_mentions(blocks: dict[str, Block]) -> list[dict[str, str]]:
    found = []
    for b in blocks.values():
        if b.type not in (BlockType.paragraph, BlockType.caption, BlockType.heading):
            continue
        if m := SUPPLEMENT_RE.search(b.text):
            start = max(0, m.start() - 60)
            found.append({"block_id": b.id, "snippet": b.text[start : m.end() + 60]})
    return found[:5]
