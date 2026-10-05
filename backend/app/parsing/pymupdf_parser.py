import re
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

from app.models import BlockType
from app.parsing.base import ParsedBlock, ParsedDocument
from app.text import get_processor, normalize

# 파싱 결과(블록 id·텍스트·문장 경계)가 바뀌는 수정을 하면 올린다
PARSER_VERSION = "pymupdf-2"

_TEXT_FLAGS = pymupdf.TEXT_DEHYPHENATE | pymupdf.TEXT_PRESERVE_WHITESPACE
_CAPTION_RE = re.compile(r"^(fig\.|figure|table|algorithm)\s*\d+", re.IGNORECASE)
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(\.\d+)*\.?|[IVX]+\.|[A-Z](\.\d+)*\.?)\s+\S")
_HEADING_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)*|[IVX]+)\.?\s")
_ABSTRACT_INLINE_RE = re.compile(r"^abstract\s*[.:\u2014\u2013-]\s*", re.IGNORECASE)
_BOLD_FLAG = 1 << 4
_HIDDEN_MIN_SIZE = 2.0  # pt
_HIDDEN_MIN_CHANNEL = 0xF0  # RGB 모두 이 값 이상이면 흰색으로 본다
_ABSTRACT_MAX_CHARS = 4000


@dataclass
class _RawBlock:
    page: int
    text: str
    bbox: tuple[float, float, float, float]
    max_size: float
    all_bold: bool
    line_count: int
    is_image: bool = False
    hidden: bool = False


@dataclass
class _PageResult:
    blocks: list[_RawBlock] = field(default_factory=list)
    hidden_blocks: int = 0  # 숨은 텍스트가 하나라도 있는 블록 수


def parse_pdf(data: bytes) -> ParsedDocument:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages = [_extract_page(page) for page in doc]
        raw = [b for p in pages for b in p.blocks]
        visible = [rb for rb in raw if not rb.hidden]
        body_size = _body_font_size(visible)
        language = _detect_language(visible)
        processor = get_processor(language)

        blocks: list[ParsedBlock] = []
        per_page: Counter[int] = Counter()
        section_id: str | None = None
        for rb in raw:
            per_page[rb.page] += 1
            block_id = f"p{rb.page}-{per_page[rb.page]}"
            block_type = _classify(rb, body_size)
            if block_type is BlockType.heading and not rb.hidden:
                section_id = block_id
            blocks.append(
                ParsedBlock(
                    id=block_id,
                    seq=len(blocks),
                    page=rb.page,
                    type=block_type,
                    text=rb.text,
                    bbox=rb.bbox,
                    section_id=section_id,
                    hidden=rb.hidden,
                    sentences=_sentences(rb, block_type, processor),
                )
            )

        _assign_heading_levels(blocks, raw)
        return ParsedDocument(
            title=_guess_title(doc, visible),
            page_count=doc.page_count,
            parser_version=PARSER_VERSION,
            language=language,
            abstract=_extract_abstract(blocks),
            hidden_text_count=sum(p.hidden_blocks for p in pages),
            blocks=blocks,
        )


def _extract_page(page: pymupdf.Page) -> _PageResult:
    page_no = page.number + 1
    result = _PageResult()
    # sort=False: 콘텐츠 스트림 순서를 유지. LaTeX PDF는 이 순서가 2단 읽기 순서와 대체로 일치한다.
    data = page.get_text("dict", flags=_TEXT_FLAGS, sort=False)
    for block in data["blocks"]:
        bbox = tuple(round(v, 2) for v in block["bbox"])
        if block["type"] == 1:
            result.blocks.append(_RawBlock(page_no, "", bbox, 0, False, 0, is_image=True))
            continue

        lines: list[str] = []
        hidden_lines: list[str] = []
        sizes: list[float] = []
        bold: list[bool] = []
        for line in block["lines"]:
            if not _is_horizontal(line["dir"]):
                continue  # arXiv 옆면 스탬프 등 회전된 텍스트는 본문이 아니다
            # 공백만 있는 span도 단어 사이 띄어쓰기라 텍스트에는 남긴다
            hidden = [s for s in line["spans"] if s["text"].strip() and _is_hidden_span(s, page.rect)]
            shown = [s for s in line["spans"] if not any(s is h for h in hidden)]
            visible_text = [s for s in shown if s["text"].strip()]
            if hidden:
                hidden_lines.append("".join(s["text"] for s in hidden).strip())
            if not visible_text:
                continue
            lines.append("".join(s["text"] for s in shown).strip())
            sizes.extend(s["size"] for s in visible_text)
            bold.extend(
                bool(s["flags"] & _BOLD_FLAG) or "bold" in s["font"].lower() for s in visible_text
            )

        if hidden_lines:
            result.hidden_blocks += 1
        if not lines:
            if hidden_lines:
                # 숨은 텍스트만 있는 블록은 기록하되 hidden으로 표시해 화면·LLM 입력에서 뺀다
                result.blocks.append(
                    _RawBlock(page_no, normalize(" ".join(hidden_lines)), bbox, 0, False, 0, hidden=True)
                )
            continue

        text = normalize(_join_lines(lines))
        if not text or _is_page_artifact(text):
            continue
        result.blocks.append(_RawBlock(page_no, text, bbox, max(sizes), all(bold), len(lines)))
    return result


def _is_hidden_span(span: dict, page_rect: pymupdf.Rect) -> bool:
    """사람 눈에 보이지 않는 텍스트. AI 리뷰어를 겨냥한 프롬프트 인젝션에 쓰인다.

    실제 배경색은 비교하지 않으므로 어두운 배경 위의 흰 글씨(그림 라벨 등)도 걸러질 수 있다.
    """
    if span["size"] < _HIDDEN_MIN_SIZE:
        return True
    color = span["color"]
    if all(((color >> shift) & 0xFF) >= _HIDDEN_MIN_CHANNEL for shift in (16, 8, 0)):
        return True
    return not pymupdf.Rect(span["bbox"]).intersects(page_rect)


def _is_horizontal(direction: tuple[float, float]) -> bool:
    return abs(direction[1]) < 0.05 and direction[0] > 0


def _join_lines(lines: list[str]) -> str:
    text = ""
    for line in lines:
        if not text:
            text = line
        elif text.endswith("-") and line[:1].islower():
            # TEXT_DEHYPHENATE가 놓친 줄끝 하이픈 처리
            text = text[:-1] + line
        else:
            text = f"{text} {line}"
    return text


def _is_page_artifact(text: str) -> bool:
    # 페이지 번호 등
    return text.isdigit() and len(text) <= 4


def _body_font_size(raw: list[_RawBlock]) -> float:
    weights: Counter[float] = Counter()
    for rb in raw:
        if not rb.is_image:
            weights[round(rb.max_size, 1)] += len(rb.text)
    return weights.most_common(1)[0][0] if weights else 10.0


def _detect_language(raw: list[_RawBlock]) -> str:
    hangul = latin = 0
    for rb in raw:
        for ch in rb.text:
            if "가" <= ch <= "힣":
                hangul += 1
            elif ch.isascii() and ch.isalpha():
                latin += 1
    total = hangul + latin
    return "ko" if total and hangul / total > 0.3 else "en"


def _classify(rb: _RawBlock, body_size: float) -> BlockType:
    if rb.is_image:
        return BlockType.figure
    if rb.hidden:
        return BlockType.paragraph
    if _CAPTION_RE.match(rb.text):
        return BlockType.caption
    if len(rb.text) < 40 and rb.max_size < body_size * 0.9:
        # 그래프 축 눈금·범례처럼 그림 안에 들어 있는 작은 글씨
        return BlockType.figure
    short = len(rb.text) <= 120 and rb.line_count <= 2 and not rb.text.endswith(".")
    if short and rb.max_size >= body_size * 1.15:
        return BlockType.heading
    if short and rb.all_bold and _NUMBERED_HEADING_RE.match(rb.text):
        return BlockType.heading
    return BlockType.paragraph


def _sentences(rb: _RawBlock, block_type: BlockType, processor) -> list[tuple[int, int]]:
    if rb.hidden or block_type is BlockType.figure:
        return []
    if block_type is BlockType.heading:
        return [(0, len(rb.text))]
    return processor.split_sentences(rb.text)


def _assign_heading_levels(blocks: list[ParsedBlock], raw: list[_RawBlock]) -> None:
    """번호가 있으면 깊이로(3 → 1, 3.2 → 2, 3.2.1 → 3), 없으면 1.

    번호 붙은 제목이 하나도 없는 논문은 글자 크기 순위로 정한다.
    """
    headings = [(b, rb) for b, rb in zip(blocks, raw, strict=True) if b.type is BlockType.heading]
    if not headings:
        return
    numbered = any(_HEADING_NUMBER_RE.match(b.text) for b, _ in headings)
    if numbered:
        for b, _ in headings:
            m = _HEADING_NUMBER_RE.match(b.text)
            b.level = min(3, m.group(1).count(".") + 1) if m else 1
        return
    sizes = sorted({round(rb.max_size, 1) for _, rb in headings}, reverse=True)
    for b, rb in headings:
        b.level = min(3, sizes.index(round(rb.max_size, 1)) + 1)


def _extract_abstract(blocks: list[ParsedBlock]) -> str | None:
    visible = [b for b in blocks if not b.hidden]
    for i, b in enumerate(visible):
        if b.type is BlockType.heading and b.text.strip(" .:").lower() == "abstract":
            parts: list[str] = []
            for nxt in visible[i + 1 :]:
                if nxt.type is BlockType.heading:
                    break
                if nxt.type is BlockType.paragraph:
                    parts.append(nxt.text)
                if sum(map(len, parts)) > _ABSTRACT_MAX_CHARS:
                    break
            return " ".join(parts)[:_ABSTRACT_MAX_CHARS] or None
        if b.type is BlockType.paragraph and _ABSTRACT_INLINE_RE.match(b.text):
            # IEEE 형식: "Abstract—We propose ..."
            return _ABSTRACT_INLINE_RE.sub("", b.text)[:_ABSTRACT_MAX_CHARS]
    return None


def _guess_title(doc: pymupdf.Document, raw: list[_RawBlock]) -> str | None:
    meta_title = normalize((doc.metadata or {}).get("title", ""))
    if len(meta_title) > 8:
        return meta_title
    first_page = [rb for rb in raw if rb.page == 1 and not rb.is_image]
    if not first_page:
        return None
    return max(first_page, key=lambda rb: rb.max_size).text[:300]
