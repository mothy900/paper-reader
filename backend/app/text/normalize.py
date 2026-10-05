"""텍스트 정규화. frontend/src/lib/normalize.ts와 동작이 같아야 한다.

두 구현은 shared/normalize_cases.json의 같은 케이스로 테스트한다.
"""

import re
import unicodedata

_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
_INVISIBLE = re.compile("[\u00ad\u200b\u200c\u200d\ufeff]")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # 합자(ﬁ → fi), 전각 문자 등
    text = _INVISIBLE.sub("", text)  # 소프트 하이픈, zero-width 문자
    text = text.translate(_QUOTES)
    return _SPACE.sub(" ", text).strip()
