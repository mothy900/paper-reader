"""수식·첨자·머리글·1쪽 앞부분 처리. Elsevier식 2단 논문 레이아웃을 흉내 낸 PDF로 검사한다."""

import pymupdf

from app.models import BlockType
from app.parsing import parse_pdf
from app.parsing.pymupdf_parser import _line_text

TITLE = "Numeric modeling of mass transfer in radish brining"
BODY = (
    "The mass transfer rate of radish during brining was evaluated based on NaCl uptake "
    "and water loss using the following equations shown below in this section."
)


def _paper(pages: int = 3, meta_title: bool = True) -> bytes:
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=595, height=794)
        # 매 쪽 반복되는 머리글
        page.insert_text((38, 42), "S.-Y. Kim et al.    Food Science 104 (2025)", fontsize=7, fontname="helv")
        page.insert_text((296, 762), str(n), fontsize=7, fontname="helv")
        if n == 1:
            page.insert_text((135, 100), "Innovative Food Science Journal", fontsize=14, fontname="helv")
            page.insert_textbox((38, 160, 488, 200), TITLE, fontsize=13, fontname="helv")
            page.insert_text((38, 220), "Si-Yeon Kim a, Sung-Roc Jang b", fontsize=10.5, fontname="helv")
            page.insert_text((38, 260), "1. Introduction", fontsize=8, fontname="hebo")
        page.insert_textbox((38, 280, 291, 340), BODY, fontsize=8, fontname="tiro")
        if n == 2:
            page.insert_text((38, 360), "2.5. Determination of mass transfer", fontsize=8, fontname="tiit")
            # 수식 (7): 분자 줄 + 아래첨자, 분모, 번호가 따로 떨어져 있다
            page.insert_text((38, 400), "ML = W", fontsize=8, fontname="tiro")
            page.insert_text((68, 402), "Mt", fontsize=5.2, fontname="tiit")
            page.insert_text((80, 400), "- W", fontsize=8, fontname="tiro")
            page.insert_text((93, 402), "M0", fontsize=5.2, fontname="tiit")
            page.insert_text((70, 412), "W0", fontsize=8, fontname="tiro")
            page.insert_text((278, 405), "(7)", fontsize=8, fontname="tiro")
            # 수식 바로 아래 소제목은 수식에 합쳐지면 안 된다
            page.insert_text((38, 425), "2.6. Prediction of mass transfer", fontsize=8, fontname="tiit")
    if meta_title:
        doc.set_metadata({"title": TITLE})
    data = doc.tobytes()
    doc.close()
    return data


def _texts(doc, block_type: BlockType) -> list[str]:
    return [b.text for b in doc.blocks if b.type is block_type]


def test_drops_running_headers() -> None:
    doc = parse_pdf(_paper())

    assert not any("Kim et al." in b.text for b in doc.blocks)


def test_front_matter_keeps_only_title_and_sections() -> None:
    doc = parse_pdf(_paper())
    headings = _texts(doc, BlockType.heading)

    assert headings[0] == TITLE
    assert "Innovative Food Science Journal" not in headings  # 저널 이름이 제목보다 커도 제외
    assert not any(h.startswith("Si-Yeon Kim") for h in headings)  # 저자 줄
    assert "1. Introduction" in headings


def test_italic_numbered_subheadings() -> None:
    doc = parse_pdf(_paper())
    by_text = {b.text: b for b in doc.blocks}

    heading = by_text["2.5. Determination of mass transfer"]
    assert heading.type is BlockType.heading
    assert heading.level == 2
    assert by_text["2.6. Prediction of mass transfer"].type is BlockType.heading


def test_merges_equation_fragments() -> None:
    doc = parse_pdf(_paper())
    equations = [b for b in doc.blocks if b.type is BlockType.equation]

    assert len(equations) == 1
    eq = equations[0]
    # 분자 줄·분모·번호가 한 블록에 (합성 PDF라 공백 위치는 실제 논문과 다를 수 있다)
    assert eq.text.startswith("ML = W") and "_{Mt}" in eq.text and "W0" in eq.text
    assert eq.text.endswith("(7)")
    assert eq.sentences == [(0, len(eq.text))]
    x0, y0, x1, y1 = eq.bbox
    assert x0 <= 38 and x1 >= 287 and y0 < 400 and y1 > 410


def _span(text: str, size: float, baseline: float) -> dict:
    return {"text": text, "size": size, "origin": (0.0, baseline)}


def test_line_text_marks_subscripts_relative_to_their_base() -> None:
    # radish 논문 수식 (6)의 분자 줄: "SG(g/gwb) ="는 분수 가운데 높이에, W_st는 그보다 위에 있다.
    # 줄 첫 글자의 기준선과 비교하면 st가 위첨자로 잘못 잡힌다.
    spans = [
        _span("SG(g/gwb) =", 8.0, 317.0),
        _span(" ", 8.0, 317.0),
        _span("W", 8.0, 311.0),
        _span("st", 5.2, 312.6),
        _span(" ", 8.0, 311.0),
        _span("\u2212", 8.0, 311.0),
        _span("W", 8.0, 311.0),
        _span("s", 5.2, 312.6),
        _span("0", 5.2, 312.6),
    ]
    assert _line_text(spans) == "SG(g/gwb) = W_{st} \u2212W_{s0}"


def test_line_text_marks_superscripts() -> None:
    spans = [_span("R", 8.0, 400.0), _span("2", 5.6, 397.0), _span(" as the metric", 8.0, 400.0)]
    assert _line_text(spans) == "R^{2} as the metric"


def test_line_text_ignores_small_text_on_the_baseline() -> None:
    # 작은 글씨여도 기준선이 같으면(예: 스몰캡) 첨자가 아니다
    spans = [_span("Model ", 8.0, 400.0), _span("AI", 6.0, 400.0)]
    assert _line_text(spans) == "Model AI"


def test_without_metadata_largest_front_text_wins() -> None:
    doc = parse_pdf(_paper(meta_title=False))

    # 메타데이터가 없으면 가장 큰 글씨를 제목으로 본다 (저널 이름이 더 크면 저널 이름이 남는 한계)
    headings = _texts(doc, BlockType.heading)
    assert headings[0] == "Innovative Food Science Journal"
    assert TITLE not in headings


def test_rotated_page_text_uses_displayed_coordinates() -> None:
    # 가로로 눕힌 표가 있는 쪽: 화면에서는 가로 글자다
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=794)
    page.insert_text((100, 700), "Table 1 Parameters of the model", fontsize=9, fontname="helv", rotate=90)
    page.set_rotation(90)
    parsed = parse_pdf(doc.tobytes())

    [block] = parsed.blocks
    assert block.text == "Table 1 Parameters of the model"
    assert block.type is BlockType.caption
    x0, y0, x1, y1 = block.bbox
    # 화면 기준(가로 794 × 세로 595) 좌표이고, 가로로 긴 글줄이다
    assert 0 <= x0 < x1 <= 794 and 0 <= y0 < y1 <= 595
    assert x1 - x0 > y1 - y0
    assert parsed.hidden_text_count == 0
