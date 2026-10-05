import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

from app.models import BlockType
from app.parsing.base import ParsedBlock, ParsedDocument

_TEXT_FLAGS = pymupdf.TEXT_DEHYPHENATE | pymupdf.TEXT_PRESERVE_WHITESPACE
_CAPTION_RE = re.compile(r"^(fig\.|figure|table|algorithm)\s*\d+", re.IGNORECASE)
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(\.\d+)*\.?|[IVX]+\.|[A-Z]\.)\s+\S")
_BOLD_FLAG = 1 << 4


@dataclass
class _RawBlock:
    page: int
    text: str
    bbox: tuple[float, float, float, float]
    max_size: float
    all_bold: bool
    line_count: int
    is_image: bool = False


def parse_pdf(data: bytes) -> ParsedDocument:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        raw = [b for page in doc for b in _extract_page(page)]
        body_size = _body_font_size(raw)
        title = _guess_title(doc, raw)

        blocks: list[ParsedBlock] = []
        per_page: Counter[int] = Counter()
        section_id: str | None = None
        for rb in raw:
            per_page[rb.page] += 1
            block_id = f"p{rb.page}-{per_page[rb.page]}"
            block_type = _classify(rb, body_size)
            if block_type is BlockType.heading:
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
                )
            )
        return ParsedDocument(title=title, page_count=doc.page_count, blocks=blocks)


def _extract_page(page: pymupdf.Page) -> list[_RawBlock]:
    page_no = page.number + 1
    # sort=False: 콘텐츠 스트림 순서를 유지. LaTeX PDF는 이 순서가 2단 읽기 순서와 대체로 일치한다.
    data = page.get_text("dict", flags=_TEXT_FLAGS, sort=False)
    out: list[_RawBlock] = []
    for block in data["blocks"]:
        bbox = tuple(round(v, 2) for v in block["bbox"])
        if block["type"] == 1:
            out.append(_RawBlock(page_no, "", bbox, 0, False, 0, is_image=True))
            continue

        lines: list[str] = []
        sizes: list[float] = []
        bold: list[bool] = []
        for line in block["lines"]:
            if not _is_horizontal(line["dir"]):
                continue  # arXiv 옆면 스탬프 등 회전된 텍스트는 본문이 아니다
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            lines.append("".join(s["text"] for s in line["spans"]).strip())
            sizes.extend(s["size"] for s in spans)
            bold.extend(bool(s["flags"] & _BOLD_FLAG) or "bold" in s["font"].lower() for s in spans)

        text = _join_lines(lines)
        if not text or _is_page_artifact(text):
            continue
        out.append(_RawBlock(page_no, text, bbox, max(sizes), all(bold), len(lines)))
    return out


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
    return re.sub(r"\s+", " ", text).strip()


def _is_page_artifact(text: str) -> bool:
    # 페이지 번호 등
    return text.isdigit() and len(text) <= 4


def _body_font_size(raw: list[_RawBlock]) -> float:
    weights: Counter[float] = Counter()
    for rb in raw:
        if not rb.is_image:
            weights[round(rb.max_size, 1)] += len(rb.text)
    return weights.most_common(1)[0][0] if weights else 10.0


def _classify(rb: _RawBlock, body_size: float) -> BlockType:
    if rb.is_image:
        return BlockType.figure
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


def _guess_title(doc: pymupdf.Document, raw: list[_RawBlock]) -> str | None:
    meta_title = (doc.metadata or {}).get("title", "").strip()
    if len(meta_title) > 8:
        return meta_title
    first_page = [rb for rb in raw if rb.page == 1 and not rb.is_image]
    if not first_page:
        return None
    return max(first_page, key=lambda rb: rb.max_size).text[:300]
