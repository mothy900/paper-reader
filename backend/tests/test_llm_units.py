import pytest

from app.llm.pricing import cost_usd, price_for
from app.llm.stream import TagStreamParser
from app.llm.tasks import render


def _feed_all(parser: TagStreamParser, chunks: list[str]) -> list[tuple[str, str]]:
    out = [(d.name, d.text) for c in chunks for d in parser.feed(c)]
    out += [(d.name, d.text) for d in parser.finish()]
    return out


def test_parser_handles_tags_split_across_chunks() -> None:
    parser = TagStreamParser(("translation", "explanation"))
    chunks = ["<transl", "ation>\n안녕", "하세요</trans", "lation>\n<explanation>쉬운 ", "설명</explanation>"]
    deltas = _feed_all(parser, chunks)

    assert "".join(t for n, t in deltas if n == "translation") == "안녕하세요"
    assert "".join(t for n, t in deltas if n == "explanation") == "쉬운 설명"
    assert parser.result() == {"translation": "안녕하세요", "explanation": "쉬운 설명"}


def test_parser_ignores_text_outside_and_unknown_tags() -> None:
    parser = TagStreamParser(("meaning",))
    _feed_all(parser, ["서론 <thinking>무시</thinking> <meaning>뜻</meaning> 끝"])

    assert parser.result() == {"meaning": "뜻"}


def test_parser_keeps_angle_brackets_inside_sections() -> None:
    parser = TagStreamParser(("symbols",))
    _feed_all(parser, ["<symbols>- a < b 일 때\n- x>0</symbols>"])

    assert parser.result() == {"symbols": "- a < b 일 때\n- x>0"}


def test_parser_flushes_unclosed_section_on_finish() -> None:
    parser = TagStreamParser(("translation",))
    deltas = _feed_all(parser, ["<translation>잘린 번역"])

    assert "".join(t for _, t in deltas) == "잘린 번역"


@pytest.mark.parametrize(
    ("model", "expected"),
    [("claude-haiku-4-5-20251001", 1.0), ("claude-sonnet-5-5", 2.0), ("claude-sonnet-5", 2.0), ("gpt-x", None)],
)
def test_price_lookup_by_prefix(model: str, expected: float | None) -> None:
    price = price_for(model)
    assert (price.input if price else None) == expected


def test_cost_usd() -> None:
    # Haiku: 1000 입력 × $1 + 200 출력 × $5 (100만 토큰당)
    assert cost_usd("claude-haiku-4-5", 1000, 200) == pytest.approx(0.002)
    assert cost_usd("unknown-model", 1000, 200) == 0.0


def test_render_does_not_touch_paper_braces() -> None:
    assert render("식: {{eq}}", {"eq": "W_{Mt} {x}"}) == "식: W_{Mt} {x}"
