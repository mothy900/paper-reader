from app.models import BlockType
from app.parsing import parse_pdf
from tests.conftest import ABSTRACT, INJECTION, make_paper_pdf


def _by_text(doc):
    return {b.text: b for b in doc.blocks}


def test_parses_title_headings_and_sections(sample_pdf: bytes) -> None:
    doc = parse_pdf(sample_pdf)

    assert doc.page_count == 1
    assert doc.title == "Sparse Attention for Everyone"

    by_text = _by_text(doc)
    intro = by_text["1 Introduction"]
    method = by_text["2 Method"]
    assert intro.type is BlockType.heading
    assert method.type is BlockType.heading
    assert by_text["Figure 1: Overview of the method."].type is BlockType.caption
    assert by_text["56-layer"].type is BlockType.figure

    # 왼쪽 단 첫 문단은 Introduction, 오른쪽 단 문단은 Method 소속
    lorem = sorted((b for b in doc.blocks if b.text.startswith("Transformers")), key=lambda b: b.bbox[0])
    assert lorem[0].section_id == intro.id
    assert lorem[1].section_id == method.id


def test_heading_levels_follow_numbering(sample_pdf: bytes) -> None:
    by_text = _by_text(parse_pdf(sample_pdf))

    assert by_text["1 Introduction"].level == 1
    assert by_text["1.1 Motivation"].level == 2
    assert by_text["2 Method"].level == 1
    assert by_text["Abstract"].level == 1
    assert by_text["Short paragraph here."].section_id == by_text["1.1 Motivation"].id


def test_extracts_abstract_and_language(sample_pdf: bytes) -> None:
    doc = parse_pdf(sample_pdf)

    assert doc.abstract == ABSTRACT
    assert doc.language == "en"


def test_splits_sentences_with_offsets(sample_pdf: bytes) -> None:
    doc = parse_pdf(sample_pdf)
    block = _by_text(doc)[ABSTRACT]

    assert [block.text[s:e] for s, e in block.sentences] == [
        "We study sparse attention.",
        "It is fast.",
        "See Fig. 2 for an overview.",
    ]
    heading = _by_text(doc)["1 Introduction"]
    assert heading.sentences == [(0, len(heading.text))]
    assert _by_text(doc)["56-layer"].sentences == []


def test_hides_invisible_text(sample_pdf: bytes) -> None:
    doc = parse_pdf(sample_pdf)

    hidden = [b for b in doc.blocks if b.hidden]
    assert doc.hidden_text_count == 2
    assert {b.text for b in hidden} == {INJECTION, "tiny secret instruction"}
    assert all(b.sentences == [] for b in hidden)
    visible_text = " ".join(b.text for b in doc.blocks if not b.hidden)
    assert "IGNORE" not in visible_text and "secret" not in visible_text


def test_clean_pdf_has_no_hidden_text() -> None:
    doc = parse_pdf(make_paper_pdf(hidden=False))

    assert doc.hidden_text_count == 0
    assert not any(b.hidden for b in doc.blocks)


def test_skips_page_numbers_and_assigns_unique_ids(sample_pdf: bytes) -> None:
    doc = parse_pdf(sample_pdf)

    assert all(b.text != "1" for b in doc.blocks)
    assert all("arXiv" not in b.text for b in doc.blocks)
    ids = [b.id for b in doc.blocks]
    assert len(ids) == len(set(ids))
    assert [b.seq for b in doc.blocks] == list(range(len(doc.blocks)))


def test_zero_width_combining_marks_are_not_hidden() -> None:
    import pymupdf

    from app.parsing.pymupdf_parser import _is_hidden_span

    page = pymupdf.Rect(0, 0, 595, 794)
    hat = {"text": "\u0302", "size": 8.0, "color": 0, "bbox": (383.0, 548.0, 383.0, 556.0)}
    off_page = {"text": "x", "size": 8.0, "color": 0, "bbox": (700.0, 10.0, 710.0, 20.0)}
    assert not _is_hidden_span(hat, page)
    assert _is_hidden_span(off_page, page)
