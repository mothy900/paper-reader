"""실제 API 없이 LLM 흐름을 검사하기 위한 가짜 Anthropic 클라이언트."""

from types import SimpleNamespace
from typing import Any


class FakeStream:
    def __init__(self, chunks: list[str], stop_reason: str, model: str, usage: tuple[int, int]) -> None:
        self.chunks = chunks
        self.stop_reason = stop_reason
        self.model = model
        self.usage = usage

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    @property
    def text_stream(self):
        async def gen():
            for c in self.chunks:
                yield c

        return gen()

    async def get_final_message(self) -> SimpleNamespace:
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            stop_details=SimpleNamespace(category="bio") if self.stop_reason == "refusal" else None,
            model=self.model,
            usage=SimpleNamespace(
                input_tokens=self.usage[0],
                output_tokens=self.usage[1],
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        )


class FakeClient:
    """messages.stream / beta.messages.stream 호출을 기록하고 정해 둔 응답을 돌려준다."""

    def __init__(self, chunks: list[str], stop_reason: str = "end_turn", usage: tuple[int, int] = (1000, 200)):
        self.chunks = chunks
        self.stop_reason = stop_reason
        self.usage = usage
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(stream=self._stream)
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **params: Any) -> FakeStream:
        self.calls.append(params)
        return FakeStream(self.chunks, self.stop_reason, params["model"], self.usage)
