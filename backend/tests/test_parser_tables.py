"""표 영역, 블록 안 제목 분리, 캡션 판별 (파서 v4)."""

import pymupdf
import pytest

from app.models import BlockType
from app.parsing import parse_pdf
from app.parsing.pymupdf_parser import _CAPTION_RE, _Line, _split_leading_heading

BODY = (
    "The samples were brined for six hours at room temperature and weighed every hour. "
    "Each condition was repeated three times and the mean values are reported in this study."
)


def _cell_rows(page: pymupdf.Page, top: float, rows: int = 4) -> None:
    """작은 글씨 숫자 셀로 된 표 본문"""
    for r in range(rows):
        y = top + r * 12
        page.insert_text((60, y), f"Group {r + 1}", fontsize=7, fontname="helv")
        page.insert_text((160, y), f"0.{r}41 ± 0.015", fontsize=7, fontname="helv")
        page.insert_text((260, y), f"1.{r}02 ± 0.018", fontsize=7, fontname="helv")


def _pdf(caption_below: bool = False) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=794)
    # Wiley식: 섹션 제목이 바로 뒤 본문과 한 텍스트 블록에 들어 있다
    page.insert_textbox(
        (40, 60, 400, 140),
        "MATERIALS AND METHODS\n" + BODY,
        fontsize=9,
        fontname="helv",
    )
    if caption_below:
        _cell_rows(page, 200)
        page.insert_text((40, 260), "Table 1. Mean values of each group", fontsize=8, fontname="helv")
    else:
        page.insert_text((40, 190), "Table 1. Mean values of each group", fontsize=8, fontname="helv")
        page.insert_text((60, 203), "Header A", fontsize=8.5, fontname="hebo")  # 셀처럼 보이지 않는 머리행
        _cell_rows(page, 216)
    page.insert_textbox((40, 300, 400, 380), BODY, fontsize=9, fontname="helv")
    page.insert_textbox((40, 390, 400, 430), "Figure 2(b) shows the viscosity curves of the six samples.", fontsize=9, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def _line(text: str, size: float, bold: bool) -> _Line:
    return _Line(text=text, bbox=(0, 0, 100, 10), x0=0, sizes=[size], bold=[bold], italic=[False])


def test_splits_heading_line_out_of_body_block() -> None:
    # hydro 논문(Wiley)의 실제 값: 12pt 굵은 제목이 9pt 본문과 한 블록에 들어 있다
    lines = [
        _line("MATERIALS AND METHODS", 12.0, True),
        _line("Six hydrocolloids were purchased from a local supplier and dissolved in", 9.0, False),
        _line("distilled water at 0.4% (w/w) with magnetic stirring for two hours.", 9.0, False),
    ]
    groups = _split_leading_heading(lines)
    assert [[ln.text for ln in g] for g in groups] == [[lines[0].text], [lines[1].text, lines[2].text]]


@pytest.mark.parametrize(
    "first",
    [
        _line("The samples were brined for six hours at room temperature.", 9.0, False),  # 그냥 본문
        _line("Sample preparation. The radish was cut into cubes", 9.0, True),  # 문장으로 끝나지 않는 굵은 줄이지만 본문도 굵음
        _line("(7)", 12.0, False),  # 수식 번호
        _line("∑ x", 14.0, False),  # 큰 수식 기호
    ],
)
def test_does_not_split_ordinary_first_lines(first: _Line) -> None:
    rest = [_line("Each condition was repeated three times and the mean values", 9.0, first.all_bold)]
    assert len(_split_leading_heading([first, *rest])) == 1


@pytest.mark.parametrize(
    ("text", "is_caption"),
    [
        ("Table 1. Power law parameters", True),
        ("Table 2: SQuAD results", True),
        ("Fig. 3 Results of the model", True),
        ("Table 1", True),
        ("Figure 4 (a) Bayesian optimization", True),
        ("Figure 2(b) shows the viscosity curves", False),
        ("Table 2 summarizes our results", False),
        ("Table 3 shows the error rates", False),
    ],
)
def test_caption_rule(text: str, is_caption: bool) -> None:
    assert bool(_CAPTION_RE.match(text)) is is_caption


@pytest.mark.parametrize("caption_below", [False, True])
def test_builds_table_region_from_caption(caption_below: bool) -> None:
    blocks = parse_pdf(_pdf(caption_below)).blocks
    [table] = [b for b in blocks if b.type is BlockType.table]

    caption = table.text[: table.sentences[0][1]]
    assert caption.startswith("Table 1. Mean values of each group")
    assert table.sentences == [(0, len(caption))]
    # 셀 텍스트가 표 블록에 들어가고, 따로 남지 않는다
    assert "0.041 ± 0.015" in table.text and "Group 4" in table.text
    assert not any(b.type is not BlockType.table and "± 0.0" in b.text for b in blocks)
    if not caption_below:
        assert "Header A" in table.text  # 영역 안의 머리행도 흡수
    # 표 다음 본문 문단은 표에 들어가지 않는다
    assert sum(1 for b in blocks if b.type is BlockType.paragraph and b.text == BODY) >= 1
    x0, y0, x1, y1 = table.bbox
    assert y1 < 300


def test_sentence_starting_with_figure_is_not_a_caption() -> None:
    blocks = parse_pdf(_pdf()).blocks
    block = next(b for b in blocks if b.text.startswith("Figure 2(b)"))
    assert block.type is BlockType.paragraph


def test_unnumbered_section_headings_are_level_one_despite_large_title() -> None:
    # hydro 논문: 24pt 제목 + 12pt 섹션 제목들 (번호 없음). 제목 때문에 섹션이 2단계로 밀리면 안 된다.
    from app.parsing.base import ParsedBlock
    from app.parsing.pymupdf_parser import _assign_heading_levels, _RawBlock

    specs = [("A Long Paper Title", 23.9, 1), ("INTRODUCTION", 12.0, 1), ("MATERIALS AND METHODS", 12.0, 2), ("Subsection", 10.0, 3)]
    blocks = [ParsedBlock(f"p{p}-{i}", i, p, BlockType.heading, t, (0, 0, 1, 1)) for i, (t, _, p) in enumerate(specs)]
    raw = [_RawBlock(p, t, (0, 0, 1, 1), size, True, 1) for t, size, p in specs]
    _assign_heading_levels(blocks, raw)
    assert [b.level for b in blocks] == [1, 1, 1, 2]
