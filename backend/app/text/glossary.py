"""논문 용어집 (LLM 없음). 약어↔풀네임, 논문이 이름 붙인 용어, 자주 나오는 핵심 용어와 그 등장 위치.

- 약어: Schwartz & Hearst (2003) 알고리즘. "large language model (LLM)"의 괄호 앞에서 풀네임을 찾는다.
- 이름 붙인 용어: "referred to as X", "we call this X" 같은 표현 뒤의 말.
- 핵심 용어: 여러 문단에 반복되는 2~3단어 명사구, 문장 중간에서도 대문자로 쓰는 이름(Transformer, ResNet).

블록 텍스트는 파싱 때 정규화되어 있으므로 등장 위치(start, end)는 화면의 블록 텍스트와 그대로 맞는다.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

# 이 섹션의 블록은 용어 추출·등장 위치에서 뺀다 (참고문헌의 저자명·학회명이 용어로 잡히지 않게)
_SKIP_SECTION = re.compile(r"^(?:[\dA-Z]+\.?\s+)?(references|bibliography|acknowledge?ments?)\b", re.IGNORECASE)
_BODY_TYPES = {"paragraph", "caption", "heading"}

Span = tuple[str, int, int]  # (block_id, start, end)


@dataclass
class TextBlock:
    id: str
    type: str
    text: str
    sentences: list[tuple[int, int]]
    section_title: str = ""


@dataclass
class Term:
    key: str  # 정규화한 대표형(소문자·단수). 약어는 풀네임 기준. 다른 논문과 같은 용어인지 비교할 때 쓴다
    label: str  # 화면 표기
    kind: str  # abbr | named | key
    short: str | None = None  # 약어
    long: str | None = None  # 풀네임
    definition: Span | None = None  # 정의한 문장 (약어·이름 붙인 용어만)
    occurrences: list[Span] = field(default_factory=list)


# --- 공통 ---------------------------------------------------------------

_STOPWORDS = set(
    """a an the of and or in on at to for from by with without as is are was were be been being this that these
    those it its we our us they their them he she his her which who whom whose what where when while than then there
    here such so not no nor but if into onto over under between among through during before after above below up down
    out off can could may might must shall should will would do does did done has have had having also only very more
    most less least many much few each every all any both either neither other another same different several various
    some one two three four five first second third new old large small high low good better best well thus however
    therefore hence since because via per e g i etc et al see fig figs figure table eq eqs section sec appendix
    respectively using used use uses based proposed show shown shows given following previous recent main several
    paper work works method methods approach approaches result results example examples case cases way ways number
    numbers set sets part parts type types kind lot times time order term terms six seven eight nine ten hundred
    thousand million billion higher lower larger smaller deeper shallower worse greater fewer longer shorter
    highest lowest largest smallest""".split()
)
# 문장 중간의 대문자 단어라도 용어가 아닌 것
_COMMON_CAPITALIZED = {
    "figure", "fig", "table", "section", "appendix", "eq", "equation", "algorithm", "theorem", "lemma",
    "definition", "proposition", "corollary", "supplementary", "january", "february", "march", "april", "may",
    "june", "july", "august", "september", "october", "november", "december", "i", "we", "our", "the",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-]*[A-Za-z]|[A-Za-z]")
# 문장부호·숫자 없이 공백 하나로만 이어진 단어 묶음 (명사구 후보는 이 안에서만 찾는다)
# "34-layer"처럼 숫자에 붙은 단어에서는 시작하지 않는다
_RUN_RE = re.compile(r"(?<![\w\-])[A-Za-z][A-Za-z\-]*(?: [A-Za-z][A-Za-z\-]*)*")


def plural(word: str) -> str:
    low = word.lower()
    if re.search(r"[^aeiou]y$", low):
        return word[:-1] + "ies"
    if re.search(r"(s|x|z|ch|sh)$", low):
        return word + "es"
    return word + "s"


def singular(word: str) -> str:
    low = word.lower()
    if len(low) > 4 and low.endswith("ies"):
        return word[:-3] + "y"
    if len(low) > 4 and re.search(r"(sses|ches|shes|xes)$", low):
        return word[:-2]
    if len(low) > 3 and low.endswith("s") and not re.search(r"(ss|us|is)$", low):
        return word[:-1]
    return word


def term_key(phrase: str) -> str:
    """대소문자·복수형·공백 차이를 없앤 비교용 키. 마지막 단어만 단수로 바꾼다 ("neural networks" → "neural network")."""
    words = phrase.lower().split()
    if not words:
        return ""
    words[-1] = singular(words[-1])
    return " ".join(words)


def _phrase_forms(phrase: str) -> list[str]:
    words = phrase.split()
    one = words[:-1] + [singular(words[-1])]
    many = words[:-1] + [plural(one[-1])]
    return list(dict.fromkeys([" ".join(one), " ".join(many), phrase]))


def _matcher(forms: list[str], case_sensitive: bool) -> re.Pattern[str]:
    alts = "|".join(re.escape(f) for f in sorted(set(forms), key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alts})(?![A-Za-z0-9])", 0 if case_sensitive else re.IGNORECASE)


def _sentence_at(block: TextBlock, pos: int) -> tuple[int, int]:
    for s, e in block.sentences:
        if s <= pos < e:
            return s, e
    return 0, len(block.text)


# --- 약어 (Schwartz-Hearst) ---------------------------------------------

_FUNCTION_WORDS = {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "with", "by", "as", "is", "are"}
_PAREN_RE = re.compile(r"\(([^()]{1,40})\)")
_SHORT_RE = re.compile(r"^(?=[^A-Z]*[A-Z])[A-Za-z0-9][A-Za-z0-9\-/&.']{1,9}$")
_ROMAN_RE = re.compile(r"^[IVXLC]+$")


def _best_long_form(short: str, candidate: str) -> str | None:
    """약어의 글자를 뒤에서부터 후보 문구에 맞춰 본다. 첫 글자는 단어의 시작과 맞아야 한다."""
    s = len(short) - 1
    i = len(candidate) - 1
    while s >= 0:
        c = short[s].lower()
        if not c.isalnum():
            s -= 1
            continue
        while i >= 0 and (
            candidate[i].lower() != c or (s == 0 and i > 0 and candidate[i - 1].isalnum())
        ):
            i -= 1
        if i < 0:
            return None
        i -= 1
        s -= 1
    start = candidate.rfind(" ", 0, i + 1) + 1
    return candidate[start:]


def _abbreviation_at(block: TextBlock, m: re.Match[str]) -> tuple[str, str] | None:
    inner = re.split(r"[;,]", m.group(1))[0].strip()
    if not _SHORT_RE.match(inner) or _ROMAN_RE.match(inner):
        return None
    # 대문자가 둘 이상이거나 숫자가 섞여야 약어다 ("(Yun, 2014)"의 저자명 제외)
    if sum(c.isupper() for c in inner) < 2 and not re.search(r"\d", inner):
        return None
    sent_start, _ = _sentence_at(block, m.start())
    before = block.text[sent_start : m.start()].rstrip()
    words = before.split()
    candidates = [inner]
    # "CNNs", "ResNets"는 단수형으로 등록한다 ("ROS"처럼 대문자 S는 약어의 일부)
    if inner.endswith("s") and sum(c.isupper() for c in inner[:-1]) >= 2:
        candidates.insert(0, inner[:-1])
    for short in candidates:
        n = min(len(short) + 5, len(short) * 2)
        window = " ".join(words[-n:])
        long = _best_long_form(short, window)
        if not long:
            continue
        long = long.strip(" -,:;\"'")
        long_words = long.split()
        if (
            len(long) <= len(short)
            or short.lower() in (w.lower() for w in long_words)
            or len(long_words) > n
            or long_words[0].lower() in _FUNCTION_WORDS
            or not re.search(r"[A-Za-z]{2}", long)
            or re.search(r"[()\[\]]", long)
        ):
            continue
        if short != inner:
            long = " ".join(long_words[:-1] + [singular(long_words[-1])])
        return short, long
    return None


def _abbreviations(blocks: list[TextBlock]) -> list[Term]:
    found: dict[str, Term] = {}
    for b in blocks:
        if b.type == "heading":
            continue
        for m in _PAREN_RE.finditer(b.text):
            hit = _abbreviation_at(b, m)
            if not hit or hit[0] in found:
                continue
            short, long = hit
            s, e = _sentence_at(b, m.start())
            found[short] = Term(
                key=term_key(long), label=short, kind="abbr", short=short, long=long, definition=(b.id, s, e)
            )
    return list(found.values())


# --- 이름 붙인 용어 -------------------------------------------------------

_NAMED_CUE = re.compile(
    r"\b(?:referred to as|refer to (?:it|this|them|these)(?: \w+)? as|we (?:call|term|dub|name)(?: (?:it|this|them|these)(?: \w+)?)?"
    r"|(?:is|are) (?:called|termed|dubbed|coined)|so-called|(?:also )?known as|which we call)\s+(?:the\s+|an?\s+)?",
    re.IGNORECASE,
)
_QUOTED = re.compile(r"[\"'“‘]([^\"'”’]{2,60})[\"'”’]")
_NAMED_STOP = _STOPWORDS - {"of"}


def _named_terms(blocks: list[TextBlock]) -> list[Term]:
    found: dict[str, Term] = {}
    for b in blocks:
        if b.type == "heading":
            continue
        for m in _NAMED_CUE.finditer(b.text):
            rest = b.text[m.end() : m.end() + 80]
            # 'we call this particular attention "Scaled Dot-Product Attention"'처럼 따옴표가 조금 뒤에 올 수 있다
            q = _QUOTED.search(rest, 0, 60)
            if q and "." in rest[: q.start()]:
                q = None
            if q:
                phrase = q.group(1).strip()
            else:
                run = _RUN_RE.match(rest)
                if not run:
                    continue
                words: list[str] = []
                for w in run.group(0).split()[:4]:
                    if w.lower() in _NAMED_STOP:
                        break
                    words.append(w)
                while words and words[-1].lower() == "of":
                    words.pop()
                phrase = " ".join(words)
            if len(phrase) < 3 or not re.search(r"[A-Za-z]{3}", phrase):
                continue
            key = term_key(phrase)
            if key in found:
                continue
            s, e = _sentence_at(b, m.start())
            found[key] = Term(key=key, label=phrase, kind="named", definition=(b.id, s, e))
    return list(found.values())


# --- 핵심 용어 (반복 명사구·고유 이름) --------------------------------------

MIN_PHRASE_COUNT = 4
MIN_NAME_COUNT = 3
MAX_KEY_TERMS = 40


def _contains_words(longer: str, shorter: str) -> bool:
    """단수화한 키끼리 비교한다. 짧은 구의 마지막 단어는 긴 구 안에서 복수일 수 있다."""
    a, b = longer.split(), shorter.split()
    return any(
        a[i : i + len(b) - 1] == b[:-1] and singular(a[i + len(b) - 1]) == b[-1] for i in range(len(a) - len(b) + 1)
    )


def _key_terms(blocks: list[TextBlock]) -> list[Term]:
    phrase_count: Counter[str] = Counter()
    phrase_blocks: dict[str, set[str]] = defaultdict(set)
    phrase_label: dict[str, Counter[str]] = defaultdict(Counter)
    name_count: Counter[str] = Counter()
    lower_count: Counter[str] = Counter()

    for b in blocks:
        if b.type == "heading":
            continue
        starts = {s for s, _ in b.sentences} | {0}
        for run in _RUN_RE.finditer(b.text):
            words = run.group(0).split()
            offsets = [m.start() + run.start() for m in re.finditer(r"\S+", run.group(0))]
            for i, w in enumerate(words):
                low = w.lower()
                lower_count[low] += w.islower()
                # 문장 첫 단어는 원래 대문자라 고유 이름인지 알 수 없다
                at_start = any(0 <= offsets[i] - s <= 1 for s in starts)
                has_inner_cap = any(c.isupper() for c in w[1:])
                if (
                    len(w) > 1
                    and w[0].isupper()
                    and low not in _COMMON_CAPITALIZED
                    and low not in _STOPWORDS
                    and (has_inner_cap or not at_start)
                    and not (i + 1 < len(words) and words[i + 1] == "et")
                ):
                    name_count[w] += 1
            for n in (2, 3, 4):
                for i in range(len(words) - n + 1):
                    gram = words[i : i + n]
                    lows = [g.lower() for g in gram]
                    if any(x in _STOPWORDS or len(x) < 2 for x in lows):
                        continue
                    # 동사로 끝나거나("pef intensity increased") 부사로 시작하는 구("extremely deep")는 명사구가 아니다
                    if lows[-1].endswith("ed") or lows[0].endswith("ly"):
                        continue
                    key = term_key(" ".join(gram))
                    phrase_count[key] += 1
                    phrase_blocks[key].add(b.id)
                    phrase_label[key][" ".join(lows[:-1] + [singular(lows[-1])])] += 1

    phrases = {
        k: c for k, c in phrase_count.items() if c >= MIN_PHRASE_COUNT and len(phrase_blocks[k]) >= 2
    }
    # 긴 구가 짧은 구의 쓰임을 대부분 덮으면 짧은 구는 뺀다 ("neural machine translation" ⊃ "machine translation")
    by_length = sorted(phrases, key=lambda k: len(k.split()), reverse=True)
    for short_key in by_length:
        n = len(short_key.split())
        if any(
            len(k.split()) > n and _contains_words(k, short_key) and phrases[k] >= 0.6 * phrases[short_key]
            for k in phrases
        ):
            phrases.pop(short_key)
    terms = [
        Term(key=k, label=phrase_label[k].most_common(1)[0][0], kind="key")
        for k, _ in sorted(phrases.items(), key=lambda kv: kv[1] * len(kv[0].split()), reverse=True)
    ]
    for name, c in name_count.most_common():
        # 소문자로도 자주 쓰면 일반 단어다 ("Attention"으로 시작하는 문장 vs 본문의 "attention")
        if c < MIN_NAME_COUNT or lower_count[name.lower()] > c:
            continue
        label = name[:-1] if name.endswith("s") and name[:-1].isupper() else name  # "GPUs" → "GPU"
        terms.append(Term(key=term_key(name), label=label, kind="key"))
    return terms[:MAX_KEY_TERMS]


# --- 조립 ---------------------------------------------------------------


def _forms(term: Term) -> tuple[list[str], list[str]]:
    """(대소문자 구분 표기, 구분 안 하는 표기). 약어는 대소문자를 지켜야 "IT"와 "it"을 섞지 않는다."""
    if term.kind == "abbr":
        assert term.short and term.long
        return [term.short, term.short + "s"], _phrase_forms(term.long)
    return [], _phrase_forms(term.label)


def find_occurrences(term: Term, blocks: list[TextBlock]) -> list[Span]:
    sensitive, insensitive = _forms(term)
    patterns = [_matcher(f, cs) for f, cs in ((sensitive, True), (insensitive, False)) if f]
    out: list[Span] = []
    for b in blocks:
        spans = sorted((m.start(), m.end()) for p in patterns for m in p.finditer(b.text))
        last_end = -1
        for s, e in spans:
            if s >= last_end:
                out.append((b.id, s, e))
                last_end = e
    return out


def body_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    return [b for b in blocks if b.type in _BODY_TYPES and not _SKIP_SECTION.match(b.section_title.strip())]


_ABSTRACT_RE = re.compile(r"^(?:\d+\.?\s*)?(abstract|introduction)\b", re.IGNORECASE)


def _after_front_matter(body: list[TextBlock]) -> list[TextBlock]:
    """저자 소속("Google Brain")이 용어로 잡히지 않게 초록·서론 앞의 블록은 추출에서 뺀다."""
    for i, b in enumerate(body):
        if _ABSTRACT_RE.match(b.text):
            return body[i:]
    return body


def build_glossary(blocks: list[TextBlock]) -> list[Term]:
    """읽기 순서로 정렬된 블록에서 용어집을 만든다. 용어는 처음 나온 순서로 돌려준다."""
    body = body_blocks(blocks)
    source = _after_front_matter(body)
    terms: list[Term] = []
    seen: set[str] = set()
    for t in _abbreviations(source):
        seen |= {t.key, t.short.lower() if t.short else ""}
        terms.append(t)
    for t in _named_terms(source) + _key_terms(source):
        if t.key in seen:
            continue
        seen.add(t.key)
        terms.append(t)
    order = {b.id: i for i, b in enumerate(body)}
    for t in terms:
        t.occurrences = find_occurrences(t, body)
    terms = [t for t in terms if t.occurrences]
    terms.sort(key=lambda t: (order[t.occurrences[0][0]], t.occurrences[0][1]))
    return terms


def match_term(terms: list[Term], text: str) -> Term | None:
    """드래그한 말이 용어집의 어느 용어인지. 약어는 대소문자까지 같아야 한다."""
    text = text.strip().strip(".,;:()[]\"'")
    if not text:
        return None
    key = term_key(text)
    for t in terms:
        if t.kind == "abbr" and text in (t.short, f"{t.short}s"):
            return t
    for t in terms:
        if t.key == key:
            return t
    return None
