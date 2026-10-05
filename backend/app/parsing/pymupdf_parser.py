import re
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

from app.models import BlockType
from app.parsing.base import ParsedBlock, ParsedDocument
from app.text import get_processor, normalize

# 파싱 결과(블록 id·텍스트·문장 경계)가 바뀌는 수정을 하면 올린다
PARSER_VERSION = "pymupdf-3"

_TEXT_FLAGS = pymupdf.TEXT_DEHYPHENATE | pymupdf.TEXT_PRESERVE_WHITESPACE
_CAPTION_RE = re.compile(r"^(fig\.|figure|table|algorithm)\s*\d+", re.IGNORECASE)
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(\.\d+)*\.?|[IVX]+\.|[A-Z](\.\d+)*\.?)\s+\S")
# 기울임체 제목은 숫자 번호만 인정한다 ("J. Smith" 같은 기울임체 이름을 제목으로 오인하지 않도록)
_DIGIT_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.?\s+\S")
_HEADING_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)*|[IVX]+)\.?\s")
# 1쪽에서 번호 없이도 제목으로 인정하는 섹션 이름. 나머지(저자 줄, 저널 이름)는 본문으로 내린다.
_FRONT_SECTION_RE = re.compile(
    r"^(abstract|introduction|background|related work|keywords?|index terms|"
    r"acknowledge?ments?|references|bibliography|conclusions?|appendix|contents)\b",
    re.IGNORECASE,
)
_EQUATION_NUMBER_RE = re.compile(r"^\(\s*(?:[A-Z]\.)?\d+(?:\.\d+)?[a-z]?\s*\)$")
_MARKUP_RE = re.compile(r"[_^]\{[^}]*\}")
_ITALIC_FLAG = 1 << 1
_SCRIPT_SIZE_RATIO = 0.8  # 줄의 주 글자 크기보다 이만큼 작으면 첨자 후보
_SCRIPT_MIN_SHIFT = 0.8  # pt. 기준선에서 이만큼 벗어나면 첨자
_EQUATION_BAND = 6.0  # pt. 수식 번호 위아래로 이 거리 안의 조각을 같은 수식으로 본다
_MARGIN_RATIO = 0.07  # 페이지 위·아래 7% 안에 완전히 들어간 블록만 머리글·바닥글 후보
_RUNNING_MIN_PAGES = 3
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
    all_italic: bool = False
    is_equation: bool = False
    last_line: str = ""
    last_line_x0: float = 0.0


@dataclass
class _PageResult:
    blocks: list[_RawBlock] = field(default_factory=list)
    hidden_blocks: int = 0  # 숨은 텍스트가 하나라도 있는 블록 수
    height: float = 0.0


def parse_pdf(data: bytes) -> ParsedDocument:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages = [_extract_page(page) for page in doc]
        _drop_running_headers(pages)
        for p in pages:
            p.blocks = _merge_equations(p.blocks)
        body_size = _body_font_size([rb for p in pages for rb in p.blocks if not rb.hidden])
        if pages:
            pages[0].blocks = _merge_title_lines(pages[0].blocks, body_size)
        raw = [b for p in pages for b in p.blocks]
        visible = [rb for rb in raw if not rb.hidden]
        language = _detect_language(visible)
        processor = get_processor(language)

        types = [_classify(rb, body_size) for rb in raw]
        _demote_front_matter(raw, types, _meta_title(doc))

        blocks: list[ParsedBlock] = []
        per_page: Counter[int] = Counter()
        section_id: str | None = None
        for rb, block_type in zip(raw, types, strict=True):
            per_page[rb.page] += 1
            block_id = f"p{rb.page}-{per_page[rb.page]}"
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
    result = _PageResult(height=page.rect.height)
    # sort=False: 콘텐츠 스트림 순서를 유지. LaTeX PDF는 이 순서가 2단 읽기 순서와 대체로 일치한다.
    data = page.get_text("dict", flags=_TEXT_FLAGS, sort=False)
    if page.rotation:
        _to_displayed_coordinates(data, page)
    for block in data["blocks"]:
        bbox = tuple(round(v, 2) for v in block["bbox"])
        if block["type"] == 1:
            result.blocks.append(_RawBlock(page_no, "", bbox, 0, False, 0, is_image=True))
            continue

        lines: list[str] = []
        last_x0 = 0.0
        hidden_lines: list[str] = []
        sizes: list[float] = []
        bold: list[bool] = []
        italic: list[bool] = []
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
            lines.append(_line_text(shown).strip())
            last_x0 = min(sp["bbox"][0] for sp in visible_text)
            sizes.extend(s["size"] for s in visible_text)
            bold.extend(
                bool(s["flags"] & _BOLD_FLAG) or "bold" in s["font"].lower() for s in visible_text
            )
            italic.extend(
                bool(s["flags"] & _ITALIC_FLAG) or any(k in s["font"].lower() for k in ("italic", "oblique"))
                for s in visible_text
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
        result.blocks.append(
            _RawBlock(
                page_no,
                text,
                bbox,
                max(sizes),
                all(bold),
                len(lines),
                all_italic=all(italic),
                last_line=normalize(lines[-1]),
                last_line_x0=last_x0,
            )
        )
    return result


def _to_displayed_coordinates(data: dict, page: pymupdf.Page) -> None:
    """회전된 페이지(가로로 눕힌 표 등)의 좌표를 화면에 보이는 방향으로 바꾼다.

    PyMuPDF는 글자 좌표를 회전 전 기준으로 준다. 그대로 쓰면 가로 글자가 세로 글자로 판단돼 빠지고,
    블록 위치가 뷰어(pdf.js는 회전된 모습으로 그린다)와 어긋난다.
    """
    m = page.rotation_matrix
    turn = pymupdf.Matrix(m.a, m.b, m.c, m.d, 0, 0)  # 방향 벡터는 회전만

    def rect(r) -> tuple[float, float, float, float]:
        return tuple(pymupdf.Rect(r) * m)

    for block in data["blocks"]:
        block["bbox"] = rect(block["bbox"])
        for line in block.get("lines", []):
            line["bbox"] = rect(line["bbox"])
            line["dir"] = tuple(pymupdf.Point(line["dir"]) * turn)
            for span in line["spans"]:
                span["bbox"] = rect(span["bbox"])
                span["origin"] = tuple(pymupdf.Point(span["origin"]) * m)


def _line_text(spans: list[dict]) -> str:
    """줄의 텍스트. 기준선에서 벗어난 작은 글씨는 첨자로 표시한다: W_{Mt}, X_{t}^{w}, R^{2}.

    PDF에는 첨자 정보가 없고 글자 크기·위치만 있다. 표시해 두면 LLM이 수식을 훨씬 잘 읽는다.
    """
    visible = [s for s in spans if s["text"].strip()]
    if not visible:
        return "".join(s["text"] for s in spans)
    main_size = max(s["size"] for s in visible)
    # 첨자는 바로 앞의 본문 크기 글자에 붙는다. 분수의 분자처럼 줄 안에서 기준선이 여러 개일 수 있다.
    base = next(s["origin"][1] for s in visible if s["size"] >= main_size * _SCRIPT_SIZE_RATIO)

    out: list[str] = []
    run_kind: str | None = None
    run: list[str] = []

    def flush() -> None:
        text = "".join(run)
        if run_kind and text.strip():
            out.append(f"{run_kind}{{{text.strip()}}}" + (" " if text.endswith(" ") else ""))
        else:
            out.append(text)
        run.clear()

    for s in spans:
        kind = None
        if s["text"].strip():
            if s["size"] >= main_size * _SCRIPT_SIZE_RATIO:
                base = s["origin"][1]
            else:
                shift = s["origin"][1] - base
                if shift > _SCRIPT_MIN_SHIFT:
                    kind = "_"
                elif shift < -_SCRIPT_MIN_SHIFT:
                    kind = "^"
        if kind != run_kind:
            flush()
            run_kind = kind
        run.append(s["text"])
    flush()
    return "".join(out)


def strip_markup(text: str) -> str:
    """첨자 표시를 지운 평문 (제목 등 사람이 읽는 곳에 쓴다)."""
    return _MARKUP_RE.sub("", text).strip()


def _drop_running_headers(pages: list[_PageResult]) -> None:
    """여러 쪽의 위·아래 여백에 반복되는 텍스트(저널 이름, 저자 약칭 등)를 지운다."""
    if len(pages) < _RUNNING_MIN_PAGES:
        return

    def key(rb: _RawBlock, height: float) -> str | None:
        if rb.is_image or rb.hidden:
            return None
        top, bottom = rb.bbox[1], rb.bbox[3]
        if bottom > height * _MARGIN_RATIO and top < height * (1 - _MARGIN_RATIO):
            return None
        return re.sub(r"\d+", "#", rb.text.lower())

    seen: dict[str, set[int]] = {}
    for p in pages:
        for rb in p.blocks:
            if k := key(rb, p.height):
                seen.setdefault(k, set()).add(rb.page)
    running = {k for k, on_pages in seen.items() if len(on_pages) >= _RUNNING_MIN_PAGES}
    for p in pages:
        p.blocks = [rb for rb in p.blocks if key(rb, p.height) not in running]


def _merge_equations(blocks: list[_RawBlock]) -> list[_RawBlock]:
    """수식 번호 "(7)"을 기준으로, 같은 높이에 흩어진 수식 조각(분자·분모·번호)을 한 블록으로 합친다.

    번호는 단독 블록일 수도("(7)"), 수식 조각과 한 블록의 마지막 줄일 수도("× 100 / (3)") 있다.
    각 조각은 세로로 가장 가까운 번호에 붙는다.
    """
    anchors = [rb for rb in blocks if rb.line_count <= 6 and _EQUATION_NUMBER_RE.match(rb.last_line)]
    for a in anchors:
        a.is_equation = True

    groups: dict[int, list[_RawBlock]] = {id(a): [] for a in anchors}
    for rb in blocks:
        if rb in anchors or rb.hidden or not _is_equation_fragment(rb):
            continue
        near = [a for a in anchors if _fits_anchor(blocks, rb, a)]
        if near:
            best = min(near, key=lambda a: abs(_center_y(a) - _center_y(rb)))
            groups[id(best)].append(rb)

    consumed: set[int] = set()
    merged: dict[int, _RawBlock] = {}  # 합친 블록을 넣을 자리(가장 앞 조각의 위치)
    for a in anchors:
        parts = groups[id(a)]
        if not parts:
            continue
        parts.sort(key=lambda rb: (rb.bbox[1], rb.bbox[0]))
        group = [*parts, a]
        merged_block = _RawBlock(
            page=a.page,
            text=" ".join(rb.text for rb in group if rb.text),
            bbox=(
                min(rb.bbox[0] for rb in group),
                min(rb.bbox[1] for rb in group),
                max(rb.bbox[2] for rb in group),
                max(rb.bbox[3] for rb in group),
            ),
            max_size=max(rb.max_size for rb in group),
            all_bold=False,
            line_count=sum(max(rb.line_count, 1) for rb in group),
            is_equation=True,
            last_line=a.last_line,
        )
        consumed.update(id(rb) for rb in group)
        merged[min(blocks.index(rb) for rb in group)] = merged_block

    out: list[_RawBlock] = []
    for i, rb in enumerate(blocks):
        if i in merged:
            out.append(merged[i])
        elif id(rb) not in consumed:
            out.append(rb)
    return out


def _merge_title_lines(blocks: list[_RawBlock], body_size: float) -> list[_RawBlock]:
    """1쪽에서 연달아 나오는 같은 크기의 큰 글씨 블록(여러 줄 제목)을 하나로 합친다."""
    out: list[_RawBlock] = []
    for rb in blocks:
        prev = out[-1] if out else None
        if (
            prev
            and not prev.is_image
            and not rb.is_image
            and prev.max_size >= body_size * 1.3
            and abs(prev.max_size - rb.max_size) < 0.3
            and 0 <= rb.bbox[1] - prev.bbox[3] < rb.max_size * 0.8
            and rb.bbox[0] < prev.bbox[2]
            and prev.bbox[0] < rb.bbox[2]
        ):
            out[-1] = _RawBlock(
                page=prev.page,
                text=f"{prev.text} {rb.text}",
                bbox=(
                    min(prev.bbox[0], rb.bbox[0]),
                    prev.bbox[1],
                    max(prev.bbox[2], rb.bbox[2]),
                    rb.bbox[3],
                ),
                max_size=prev.max_size,
                all_bold=prev.all_bold and rb.all_bold,
                line_count=prev.line_count + rb.line_count,
                all_italic=prev.all_italic and rb.all_italic,
                last_line=rb.last_line,
                last_line_x0=rb.last_line_x0,
            )
        else:
            out.append(rb)
    return out


def _is_equation_fragment(rb: _RawBlock) -> bool:
    if rb.is_image:
        return True
    if rb.line_count > 4 or len(rb.text) > 250:
        return False
    # 수식 바로 아래의 소제목("2.4. Total mass ...")을 끌어오지 않는다
    return not ((rb.all_bold or rb.all_italic) and _NUMBERED_HEADING_RE.match(rb.text))


def _fits_anchor(blocks: list[_RawBlock], rb: _RawBlock, anchor: _RawBlock) -> bool:
    """조각이 번호와 같은 단에서, 번호 왼쪽에, 번호와 비슷한 높이에 있는지."""
    x0, y0, x1, y1 = rb.bbox
    _, ay0, _, ay1 = anchor.bbox
    number_x0 = anchor.last_line_x0 or anchor.bbox[0]
    return (
        x0 >= _column_left(blocks, anchor) - 2
        and x1 <= number_x0 + 2
        and y1 >= ay0 - _EQUATION_BAND
        and y0 <= ay1 + _EQUATION_BAND
    )


def _center_y(rb: _RawBlock) -> float:
    return (rb.bbox[1] + rb.bbox[3]) / 2


def _column_left(blocks: list[_RawBlock], num: _RawBlock) -> float:
    """수식 번호가 속한 단의 왼쪽 끝. 번호를 가로로 포함하는 가장 가까운 본문 문단으로 판단한다."""
    nx0, ny0, nx1, _ = num.bbox
    columns = [
        rb
        for rb in blocks
        if not rb.is_image and rb.line_count >= 3 and rb.bbox[0] <= nx0 and rb.bbox[2] >= nx1 - 6
    ]
    if not columns:
        return 0.0
    return min(columns, key=lambda rb: abs(rb.bbox[1] - ny0)).bbox[0]


def _is_hidden_span(span: dict, page_rect: pymupdf.Rect) -> bool:
    """사람 눈에 보이지 않는 텍스트. AI 리뷰어를 겨냥한 프롬프트 인젝션에 쓰인다.

    실제 배경색은 비교하지 않으므로 어두운 배경 위의 흰 글씨(그림 라벨 등)도 걸러질 수 있다.
    """
    if span["size"] < _HIDDEN_MIN_SIZE:
        return True
    color = span["color"]
    if all(((color >> shift) & 0xFF) >= _HIDDEN_MIN_CHANNEL for shift in (16, 8, 0)):
        return True
    # 완전히 페이지 바깥인 경우만. 폭이 0인 글자(모자 기호 같은 결합 문자)는 Rect.intersects가 항상 False라 쓰지 않는다.
    x0, y0, x1, y1 = span["bbox"]
    return x1 < page_rect.x0 or x0 > page_rect.x1 or y1 < page_rect.y0 or y0 > page_rect.y1


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
    if rb.is_equation:
        return BlockType.equation
    if _CAPTION_RE.match(rb.text):
        return BlockType.caption
    if len(rb.text) < 40 and rb.max_size < body_size * 0.9:
        # 그래프 축 눈금·범례처럼 그림 안에 들어 있는 작은 글씨
        return BlockType.figure
    no_period = not rb.text.endswith(".")
    short = len(rb.text) <= 120 and rb.line_count <= 2 and no_period
    if short and rb.max_size >= body_size * 1.15:
        return BlockType.heading
    # 논문 제목처럼 아주 큰 글씨는 세 줄까지 제목으로 본다
    if no_period and len(rb.text) <= 250 and rb.line_count <= 3 and rb.max_size >= body_size * 1.3:
        return BlockType.heading
    if short and rb.all_bold and _NUMBERED_HEADING_RE.match(rb.text):
        return BlockType.heading
    if short and rb.all_italic and _DIGIT_HEADING_RE.match(rb.text):
        return BlockType.heading  # Elsevier 등: "2.5. Determination of ..."
    return BlockType.paragraph


def _demote_front_matter(raw: list[_RawBlock], types: list[BlockType], meta_title: str) -> None:
    """1쪽의 번호 없는 큰 글씨 중 논문 제목과 일반 섹션 이름만 제목으로 남긴다.

    저자 줄·저널 이름처럼 글씨만 큰 텍스트가 목차에 섞이지 않게 한다.
    """
    meta_key = _loose(meta_title)
    if meta_key:
        # 메타데이터 제목과 일치하는 블록은 글씨 크기와 상관없이 논문 제목이다
        for i, rb in enumerate(raw):
            if rb.page == 1 and not rb.is_image and _loose(strip_markup(rb.text)) == meta_key:
                types[i] = BlockType.heading
    first = [i for i, rb in enumerate(raw) if rb.page == 1 and types[i] is BlockType.heading]
    candidates = [
        i
        for i in first
        if not _HEADING_NUMBER_RE.match(raw[i].text) and not _FRONT_SECTION_RE.match(raw[i].text)
    ]
    if not candidates:
        return
    matches = [i for i in candidates if meta_key and _loose(strip_markup(raw[i].text)) == meta_key]
    title = matches[0] if matches else max(candidates, key=lambda i: raw[i].max_size)
    for i in candidates:
        if i != title:
            types[i] = BlockType.paragraph


def _loose(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _sentences(rb: _RawBlock, block_type: BlockType, processor) -> list[tuple[int, int]]:
    if rb.hidden or block_type is BlockType.figure:
        return []
    if block_type in (BlockType.heading, BlockType.equation):
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


def _meta_title(doc: pymupdf.Document) -> str:
    title = normalize((doc.metadata or {}).get("title", ""))
    return title if len(title) > 8 else ""


def _guess_title(doc: pymupdf.Document, raw: list[_RawBlock]) -> str | None:
    if meta_title := _meta_title(doc):
        return meta_title
    first_page = [rb for rb in raw if rb.page == 1 and not rb.is_image]
    if not first_page:
        return None
    return strip_markup(max(first_page, key=lambda rb: rb.max_size).text)[:300]
