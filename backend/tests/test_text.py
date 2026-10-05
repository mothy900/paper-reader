import json
from pathlib import Path

import pytest

from app.text import normalize
from app.text.processor import EnglishProcessor

CASES = json.loads((Path(__file__).parents[2] / "shared" / "normalize_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_normalize_shared_cases(case: dict) -> None:
    assert normalize(case["input"]) == case["expected"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "As shown in Fig. 3, the model converges. See Eq. (2) for details.",
            ["As shown in Fig. 3, the model converges.", "See Eq. (2) for details."],
        ),
        (
            "Vaswani et al. proposed the Transformer. It uses attention, i.e. a weighted sum.",
            ["Vaswani et al. proposed the Transformer.", "It uses attention, i.e. a weighted sum."],
        ),
        (
            "Results are in Sec. 4.2 and Table 1. The error drops to 3.57% on ImageNet.",
            ["Results are in Sec. 4.2 and Table 1.", "The error drops to 3.57% on ImageNet."],
        ),
        (
            "Deep networks are hard to train [22, 21]. We present a residual framework.",
            ["Deep networks are hard to train [22, 21].", "We present a residual framework."],
        ),
        (
            "Models such as BERT, GPT, etc. are pre-trained. Our approach differs.",
            ["Models such as BERT, GPT, etc. are pre-trained.", "Our approach differs."],
        ),
        (
            "Work by J. Smith shows this. (See the appendix.) Then we stop!",
            ["Work by J. Smith shows this.", "(See the appendix.)", "Then we stop!"],
        ),
        ("No terminal punctuation", ["No terminal punctuation"]),
        ("", []),
    ],
)
def test_split_sentences(text: str, expected: list[str]) -> None:
    spans = EnglishProcessor().split_sentences(text)
    assert [text[s:e] for s, e in spans] == expected
