from app.text.glossary import TextBlock, build_glossary, match_term, plural, singular, term_key


def _block(i: int, text: str, type_: str = "paragraph", section: str = "1 Introduction") -> TextBlock:
    return TextBlock(f"p1-{i}", type_, text, [(0, len(text))], section)


def _by_label(terms):
    return {t.label: t for t in terms}


def test_abbreviation_long_form_and_occurrences() -> None:
    blocks = [
        _block(0, "Abstract", "heading"),
        _block(1, "We train a large language model (LLM) on text."),
        _block(2, "The LLM is fast. Two LLMs agree. The word llm in lowercase is not it."),
    ]
    t = _by_label(build_glossary(blocks))["LLM"]
    assert (t.kind, t.short, t.long, t.key) == ("abbr", "LLM", "large language model", "large language model")
    assert t.definition == ("p1-1", 0, len(blocks[1].text))
    found = [blocks[int(b[-1])].text[s:e] for b, s, e in t.occurrences]
    assert found == ["large language model", "LLM", "LLM", "LLMs"]


def test_plural_abbreviation_is_registered_singular() -> None:
    t = _by_label(build_glossary([_block(1, "We use convolutional neural networks (CNNs) here.")]))["CNN"]
    assert t.long == "convolutional neural network"


def test_rejects_citations_and_non_abbreviations() -> None:
    terms = build_glossary(
        [_block(1, "As shown before (Yun, 2014) and in Table 2 (II) the result (p < 0.05) holds (see Fig. 1).")]
    )
    assert not [t for t in terms if t.kind == "abbr"]


def test_named_term_after_cue() -> None:
    blocks = [_block(1, 'We call this particular attention "Scaled Dot-Product Attention" in this work.')]
    t = _by_label(build_glossary(blocks))["Scaled Dot-Product Attention"]
    assert t.kind == "named" and t.definition is not None


def test_repeated_phrases_and_names_skip_references_and_front_matter() -> None:
    para = "The residual function is learned by stacked layers. We use the Transformer here."
    blocks = (
        [_block(0, "Google Brain Google Brain Google Brain", section="")]
        + [_block(0, "Abstract", "heading", section="")]
        + [_block(i, para) for i in range(1, 5)]
        + [_block(9, "Residual function residual function residual function residual function.", section="References")]
    )
    labels = _by_label(build_glossary(blocks))
    assert "residual function" in labels and "Transformer" in labels
    assert "Google" not in labels and "google brain" not in labels
    # 참고문헌의 등장은 세지 않는다
    assert len(labels["residual function"].occurrences) == 4


def test_match_term_and_forms() -> None:
    terms = build_glossary([_block(1, "A recurrent neural network (RNN) is used. Many RNNs exist.")])
    assert match_term(terms, "RNNs").short == "RNN"
    assert match_term(terms, "Recurrent neural networks").short == "RNN"
    assert match_term(terms, "rnn") is None  # 약어는 대소문자까지 같아야 한다
    assert (plural("query"), plural("box"), singular("analyses"), singular("process")) == ("queries", "boxes", "analyse", "process")
    assert term_key("Neural  Networks") == "neural network"
