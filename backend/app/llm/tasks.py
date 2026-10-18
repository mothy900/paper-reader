"""LLM 작업 정의. 모델·프롬프트 버전·출력 섹션·분량을 한곳에서 관리한다."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
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
    # 정해 두면 상세도와 상관없이 이 모델을 쓴다 (논문 단위 작업은 정확도가 중요해 항상 Sonnet)
    model: str | None = None
    effort: str = "low"  # Sonnet일 때만 적용
    # 있으면 태그 스트림 대신 이 스키마의 JSON으로 받는다 (구조화 출력)
    json_schema: dict[str, Any] | None = field(default=None, hash=False, compare=False)
    system_file: str = "system.md"


EXPLAIN_WORD = Task("explain_word", "explain_word.md", "1", ("in_paper", "general", "plain"), 700, 3000)
EXPLAIN_SENTENCE = Task(
    "explain_sentence", "explain_sentence.md", "1", ("translation", "explanation", "role", "terms"), 1200, 5000
)
EXPLAIN_EQUATION = Task(
    "explain_equation", "explain_equation.md", "1", ("meaning", "symbols", "intuition"), 1200, 5000
)
EXPLAIN_TABLE = Task("explain_table", "explain_table.md", "1", ("summary", "how_to_read", "key_points"), 1500, 5000)
TRANSLATE = Task("translate", "translate.md", "1", ("translation",), 2000, 2000)


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    """구조화 출력은 모든 객체에 additionalProperties: false와 전체 required를 요구한다."""
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


_EVIDENCE = {
    "type": "array",
    "items": _obj({"ref": {"type": "string"}, "quote": {"type": "string"}}),
}
_FIELD = _obj(
    {
        "value": {"type": "string"},
        "status": {"type": "string", "enum": ["stated", "inferred", "not_stated", "not_applicable"]},
        "calculation": {"type": "string"},
        "evidence": _EVIDENCE,
    }
)
DATA_FIELDS = ("inputs", "outputs", "sample_size", "validation", "metrics")

PREP_DATA_SCHEMA = _obj(
    {
        "applicable": {"type": "boolean"},
        "not_applicable_reason": {"type": "string"},
        "fields": _obj({name: _FIELD for name in DATA_FIELDS}),
        "warnings": {"type": "array", "items": _obj({"text": {"type": "string"}, "evidence": _EVIDENCE})},
        "questions": {"type": "array", "items": {"type": "string"}},
    }
)
PREP_CONCEPTS_SCHEMA = _obj(
    {
        "concepts": {
            "type": "array",
            "items": _obj(
                {
                    "name": {"type": "string"},
                    "original": {"type": "string"},
                    "what": {"type": "string"},
                    "why": {"type": "string"},
                    "section_ref": {"type": "string"},
                }
            ),
        }
    }
)

PREP_DATA = Task(
    "prep_data", "prep_data.md", "2", (), 16000, 16000,
    model=SONNET, effort="medium", json_schema=PREP_DATA_SCHEMA, system_file="prep_system.md",
)  # fmt: skip
PREP_CONCEPTS = Task(
    "prep_concepts", "prep_concepts.md", "2", (), 12000, 12000,
    model=SONNET, effort="low", json_schema=PREP_CONCEPTS_SCHEMA, system_file="prep_system.md",
)  # fmt: skip

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


def system_prompt(background: str, level: str, detail: Detail, file: str = "system.md") -> str:
    return render(
        _template(file),
        {
            "background": background.strip() or "알려지지 않음",
            "level": _LEVEL.get(level, _LEVEL["beginner"]),
            "depth": _DEPTH[detail],
        },
    )


def user_prompt(task: Task, values: dict[str, str]) -> str:
    return render(_template(task.prompt_file), values)
