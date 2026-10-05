from app.models import BlockType
from app.parsing import parse_pdf


def test_parses_title_headings_and_sections(sample_pdf: bytes) -> None:
    doc = parse_pdf(sample_pdf)

    assert doc.page_count == 1
    assert doc.title == "Sparse Attention for Everyone"

    by_text = {b.text: b for b in doc.blocks}
    intro = by_text["1 Introduction"]
    method = by_text["2 Method"]
    assert intro.type is BlockType.heading
    assert method.type is BlockType.heading
    assert by_text["Figure 1: Overview of the method."].type is BlockType.caption
    assert by_text["56-layer"].type is BlockType.figure

    paragraphs = [b for b in doc.blocks if b.type is BlockType.paragraph]
    assert len(paragraphs) == 2
    # 왼쪽 단 문단은 Introduction, 오른쪽 단 문단은 Method 소속
    left, right = sorted(paragraphs, key=lambda b: b.bbox[0])
    assert left.section_id == intro.id
    assert right.section_id == method.id


def test_skips_page_numbers_and_assigns_unique_ids(sample_pdf: bytes) -> None:
    doc = parse_pdf(sample_pdf)

    assert all(b.text != "1" for b in doc.blocks)
    assert all("arXiv" not in b.text for b in doc.blocks)
    ids = [b.id for b in doc.blocks]
    assert len(ids) == len(set(ids))
    assert [b.seq for b in doc.blocks] == list(range(len(doc.blocks)))
