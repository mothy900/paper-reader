"""<section>…</section> 태그로 나뉜 출력을 스트리밍 중에 섹션별로 자른다.

JSON 대신 태그를 쓰는 이유: 반쯤 받은 JSON은 화면에 그리기 어렵지만, 태그는 받는 즉시 섹션에 붙일 수 있다.
"""

import re
from dataclasses import dataclass

_OPEN = re.compile(r"<([a-z_]+)>")


@dataclass
class SectionDelta:
    name: str
    text: str


class TagStreamParser:
    def __init__(self, sections: tuple[str, ...]) -> None:
        self.sections = sections
        self.buffer = ""
        self.current: str | None = None
        self.collected: dict[str, str] = {}

    def feed(self, chunk: str) -> list[SectionDelta]:
        self.buffer += chunk
        out: list[SectionDelta] = []
        while True:
            if self.current is None:
                m = _OPEN.search(self.buffer)
                if not m:
                    # 태그 밖 텍스트는 버리되, 잘린 태그 조각("<transl")은 남긴다
                    cut = self.buffer.rfind("<")
                    self.buffer = self.buffer[cut:] if cut != -1 else ""
                    return out
                if m.group(1) in self.sections:
                    self.current = m.group(1)
                self.buffer = self.buffer[m.end() :]
                continue

            close = f"</{self.current}>"
            idx = self.buffer.find(close)
            if idx != -1:
                self._emit(out, self.buffer[:idx])
                self.buffer = self.buffer[idx + len(close) :]
                self.current = None
                continue
            # 닫는 태그가 청크 경계에서 잘렸을 수 있으니 그 길이만큼은 남겨 둔다
            safe = len(self.buffer) - (len(close) - 1)
            if safe > 0:
                self._emit(out, self.buffer[:safe])
                self.buffer = self.buffer[safe:]
            return out

    def finish(self) -> list[SectionDelta]:
        """스트림이 끝났는데 닫히지 않은 섹션(max_tokens 등)의 남은 텍스트."""
        out: list[SectionDelta] = []
        if self.current is not None:
            self._emit(out, self.buffer)
        self.buffer = ""
        return out

    def _emit(self, out: list[SectionDelta], text: str) -> None:
        if not text:
            return
        name = self.current
        # 섹션 앞쪽 줄바꿈은 버린다 (<translation>\n번역…)
        if not self.collected.get(name):
            text = text.lstrip("\n")
            if not text:
                return
        self.collected[name] = self.collected.get(name, "") + text
        out.append(SectionDelta(name, text))

    def result(self) -> dict[str, str]:
        return {k: v.strip() for k, v in self.collected.items() if v.strip()}
