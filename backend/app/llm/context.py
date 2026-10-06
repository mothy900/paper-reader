"""작업별 최소 컨텍스트. 토큰을 아끼기 위해 논문 전체가 아니라 필요한 조각만 보낸다."""

import re
from dataclasses import dataclass, field

import pymupdf
from sqlmodel import Session, col, select

from app.llm.tasks import EXPLAIN_EQUATION, EXPLAIN_SENTENCE, EXPLAIN_WORD, Task
from app.models import Block, BlockType, Paper, Sentence
from app.storage import Storage

MAX_SELECTION_CHARS = 2500
MAX_PARAGRAPH_CHARS = 3000
MAX_MENTIONS = 3
WORD_MAX_WORDS = 3


@dataclass
class FocusRange:
    block_id: str
    start: int
    end: int


@dataclass
class Focus:
    source: str  # selection | block
    text: str
    block_ids: list[str]
    ranges: list[FocusRange]
    sentence_ids: list[str] = field(default_factory=list)


@dataclass
class Prepared:
    task: Task
    values: dict[str, str]
    image_png: bytes | None = None


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " …"


def choose_task(focus: Focus, blocks: dict[str, Block]) -> Task:
    if any(blocks[b].type is BlockType.equation for b in focus.block_ids if b in blocks):
        return EXPLAIN_EQUATION
    words = re.findall(r"\S+", focus.text)
    if focus.source == "selection" and 0 < len(words) <= WORD_MAX_WORDS and len(focus.sentence_ids) <= 1:
        return EXPLAIN_WORD
    return EXPLAIN_SENTENCE


def prepare_explain(session: Session, storage: Storage, paper: Paper, focus: Focus) -> Prepared:
    all_blocks = list(
        session.exec(
            select(Block)
            .where(Block.paper_id == paper.id, col(Block.hidden).is_(False))
            .order_by(col(Block.seq))
        )
    )
    blocks = {b.id: b for b in all_blocks}
    focused = [blocks[b] for b in focus.block_ids if b in blocks]
    if not focused:
        raise ValueError("포커스한 블록을 찾지 못했습니다.")
    first = focused[0]
    section_title = blocks[first.section_id].text if first.section_id in blocks else ""
    task = choose_task(focus, blocks)

    if task is EXPLAIN_EQUATION:
        eq = next(b for b in focused if b.type is BlockType.equation)
        idx = all_blocks.index(eq)
        before = next((b.text for b in reversed(all_blocks[:idx]) if b.type is BlockType.paragraph), "")
        after = next((b.text for b in all_blocks[idx + 1 :] if b.type is BlockType.paragraph), "")
        return Prepared(
            task,
            {
                "section_title": section_title,
                "equation_text": eq.text,
                "before": _clip(before, 1200),
                "after": _clip(after, 1200),
            },
            image_png=_render_block(storage, paper, eq),
        )

    paragraph = _clip(" ".join(b.text for b in focused), MAX_PARAGRAPH_CHARS)
    selection = _clip(focus.text if focus.source == "selection" else paragraph, MAX_SELECTION_CHARS)

    if task is EXPLAIN_WORD:
        sentence = _sentence_text(session, paper.id, focus, blocks) or paragraph
        return Prepared(
            task,
            {
                "section_title": section_title,
                "sentence": sentence,
                "paragraph": paragraph,
                "mentions": _other_mentions(all_blocks, focus.text, exclude=set(focus.block_ids)),
                "selection": selection,
            },
        )

    return Prepared(
        task,
        {
            "abstract": _clip(paper.abstract or "", 1500),
            "section_title": section_title,
            "paragraph": paragraph,
            "selection": selection,
        },
    )


def prepare_translate(session: Session, paper: Paper, block_id: str) -> dict[str, str]:
    block = session.get(Block, (paper.id, block_id))
    if block is None or block.hidden:
        raise ValueError("문단을 찾지 못했습니다.")
    section = session.get(Block, (paper.id, block.section_id)) if block.section_id else None
    return {"section_title": section.text if section else "", "paragraph": block.text}


def _sentence_text(session: Session, paper_id: str, focus: Focus, blocks: dict[str, Block]) -> str:
    if not focus.sentence_ids:
        return ""
    block_id, idx = focus.sentence_ids[0].rsplit(":", 1)
    s = session.get(Sentence, (paper_id, block_id, int(idx)))
    block = blocks.get(block_id)
    return block.text[s.start : s.end] if s and block else ""


def _other_mentions(all_blocks: list[Block], term: str, exclude: set[str]) -> str:
    """같은 단어가 나오는 다른 문장들(앞쪽부터). 논문이 그 단어를 어떻게 정의·사용하는지 단서가 된다."""
    needle = term.strip().lower()
    if len(needle) < 2:
        return ""
    found: list[str] = []
    for b in all_blocks:
        if b.id in exclude or b.type not in (BlockType.paragraph, BlockType.caption):
            continue
        low = b.text.lower()
        pos = low.find(needle)
        if pos == -1:
            continue
        start = max(low.rfind(". ", 0, pos) + 2, 0)
        end = low.find(". ", pos)
        found.append(_clip(b.text[start : end + 1 if end != -1 else len(b.text)], 400))
        if len(found) >= MAX_MENTIONS:
            break
    return "\n".join(f"- {s}" for s in found)


def _render_block(storage: Storage, paper: Paper, block: Block, dpi: int = 200) -> bytes | None:
    """블록 영역을 PNG로 잘라낸다. 블록 좌표는 화면 방향 기준이라 회전된 페이지는 되돌려서 자른다."""
    try:
        with pymupdf.open(stream=storage.load(paper.file_key), filetype="pdf") as doc:
            page = doc[block.page - 1]
            clip = pymupdf.Rect(block.x0 - 4, block.y0 - 4, block.x1 + 4, block.y1 + 4)
            if page.rotation:
                clip = clip * page.derotation_matrix
            return page.get_pixmap(clip=clip, dpi=dpi).tobytes("png")
    except Exception:  # noqa: BLE001 - 이미지가 없어도 텍스트로 해설할 수 있다
        return None
