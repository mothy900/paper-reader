"""언어별 텍스트 처리. 지금은 영어만 구현하고, 한국어는 같은 인터페이스로 추가한다."""

import re
from typing import Protocol

Span = tuple[int, int]


class TextProcessor(Protocol):
    def split_sentences(self, text: str) -> list[Span]: ...


# 뒤에 대문자·숫자가 와도 문장 끝이 아닌 약어 (소문자로 비교)
_ABBREVIATIONS = {
    "fig", "figs", "eq", "eqs", "sec", "secs", "tab", "tabs", "ref", "refs",
    "no", "nos", "vol", "pp", "ch", "app", "approx", "resp", "vs", "cf",
    "e.g", "i.e", "dr", "mr", "ms", "prof", "st", "jr", "inc", "ltd", "co",
}
# 문장 끝 후보: 종결 부호 (+ 닫는 괄호·따옴표) + 공백 + (여는 괄호·따옴표) + 대문자
_BOUNDARY = re.compile(r"""[.!?]['")\]]*(?=\s+['"(\[]?[A-Z])""")
_WORD_BEFORE = re.compile(r"([A-Za-z.]+)\.$")


class EnglishProcessor:
    def split_sentences(self, text: str) -> list[Span]:
        spans: list[Span] = []
        start = 0
        for m in _BOUNDARY.finditer(text):
            if m.group(0)[0] == "." and self._is_abbreviation(text[start : m.start() + 1]):
                continue
            spans.append((start, m.end()))
            start = m.end()
            while start < len(text) and text[start].isspace():
                start += 1
        if start < len(text):
            spans.append((start, len(text.rstrip())))
        return [s for s in spans if s[1] > s[0]]

    @staticmethod
    def _is_abbreviation(chunk: str) -> bool:
        m = _WORD_BEFORE.search(chunk)
        if not m:
            return False
        word = m.group(1)
        # "J. Smith"처럼 이니셜 한 글자
        if len(word) == 1 and word.isupper():
            return True
        return word.lower() in _ABBREVIATIONS


def get_processor(language: str) -> TextProcessor:
    # 한국어 처리기는 7단계에서 추가. 그 전까지는 영어 규칙으로 처리한다.
    return EnglishProcessor()
