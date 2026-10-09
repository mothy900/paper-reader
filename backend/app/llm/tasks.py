"""LLM 작업 정의. 모델·프롬프트 버전·출력 섹션·분량을 한곳에서 관리한다."""

from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5-5"


class Detail(StrEnum):
    basic = "basic"  # Haiku, 짧게
    deep = "deep"  # Sonnet, 자세히 ("더 자세히" 버튼)


@dataclass(frozen=True)
class Task:
    name: str
    prompt_file: str
    # 프롬프트나 출력 형식을 바꾸면 올린다. 결과 캐시 키에 들어가므로 이전 결과를 재사용하지 않게 된다.
    prompt_version: str
    sections: tuple[str, ...]
    max_tokens_basic: int
    max_tokens_deep: int


EXPLAIN_WORD = Task("explain_word", "explain_word.md", "1", ("in_paper", "general", "plain"), 700, 3000)
EXPLAIN_SENTENCE = Task(
    "explain_sentence", "explain_sentence.md", "1", ("translation", "explanation", "role", "terms"), 1200, 5000
)
EXPLAIN_EQUATION = Task(
    "explain_equation", "explain_equation.md", "1", ("meaning", "symbols", "intuition"), 1200, 5000
)
TRANSLATE = Task("translate", "translate.md", "1", ("translation",), 2000, 2000)

_DEPTH = {
    Detail.basic: "각 태그를 2~3문장 안으로 짧게 쓴다.",
    Detail.deep: "각 태그를 충분히 자세히 쓴다. 필요하면 예시와 배경 설명을 더한다.",
}
_LEVEL = {
    "beginner": "해당 분야를 처음 접하는 사람",
    "intermediate": "기초는 알지만 이 주제는 낯선 사람",
    "expert": "이 분야를 공부한 사람",
}


def model_for(detail: Detail) -> str:
    return SONNET if detail is Detail.deep else HAIKU


def max_tokens_for(task: Task, detail: Detail) -> int:
    return task.max_tokens_deep if detail is Detail.deep else task.max_tokens_basic


@cache
def _template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def render(template: str, values: dict[str, str]) -> str:
    """{{name}} 자리표시자를 채운다. 논문 텍스트의 중괄호(W_{Mt})와 겹치지 않게 str.format을 쓰지 않는다."""
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def system_prompt(background: str, level: str, detail: Detail) -> str:
    return render(
        _template("system.md"),
        {
            "background": background.strip() or "알려지지 않음",
            "level": _LEVEL.get(level, _LEVEL["beginner"]),
            "depth": _DEPTH[detail],
        },
    )


def user_prompt(task: Task, values: dict[str, str]) -> str:
    return render(_template(task.prompt_file), values)
