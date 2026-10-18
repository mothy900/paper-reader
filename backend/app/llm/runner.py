"""LLM 실행기. 결과 캐시 → API 호출(스트리밍) → 호출 기록·비용 계산을 한곳에서 처리한다.

이벤트(SSE로 그대로 내보낸다):
  meta     {task, model, cached}
  section  {name, delta}          섹션 텍스트 조각
  done     {model, cached, cost_usd, input_tokens, output_tokens}
  refused  {category, message}    안전 분류기 거절 (앞서 보낸 조각은 버려야 한다)
  error    {message}
"""

import base64
import hashlib
import json
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic
from sqlmodel import Session

from app.db import engine
from app.llm.pricing import cost_usd
from app.llm.stream import TagStreamParser
from app.llm.tasks import SONNET, Detail, Task, max_tokens_for, model_for, system_prompt, user_prompt
from app.models import LlmCall, LlmResult

Event = dict[str, Any]
PostProcess = Callable[[dict[str, Any]], dict[str, Any]]

# Sonnet 5.5가 일부 범주(사이버 등)에서 오탐으로 거절하면 서버가 다른 모델로 다시 시도한다.
# 생물학(bio) 범주 거절은 대체하지 않으므로 refused 이벤트 처리가 여전히 필요하다.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_REFUSAL_MESSAGE = (
    "이 부분은 모델의 안전 정책 때문에 해설하지 못했어요. "
    "생명과학·보안 분야 논문에서 가끔 일어나는 오탐일 수 있어요. 다른 문장을 골라 보세요."
)


@dataclass
class RunRequest:
    task: Task
    detail: Detail
    values: dict[str, str]
    background: str
    level: str
    user_id: str
    paper_id: str | None
    image_png: bytes | None = None
    # 이름표가 붙은 추가 이미지 (예: 데이터 뼈대 카드의 표 이미지 [("table:p9-1", png)])
    labeled_images: list[tuple[str, bytes | None]] = field(default_factory=list)

    @property
    def model(self) -> str:
        return self.task.model or model_for(self.detail)

    def cache_key(self) -> str:
        payload = {
            "task": self.task.name,
            "prompt_version": self.task.prompt_version,
            "model": self.model,
            "detail": self.detail.value,
            "values": self.values,
            "profile": [self.background.strip(), self.level],
            "image": hashlib.sha256(self.image_png).hexdigest() if self.image_png else None,
            # 표 이미지는 같은 PDF·같은 영역이면 같으므로 id만 넣는다 (조회 때 이미지를 그리지 않아도 키를 알 수 있게)
            "images": [label for label, _ in self.labeled_images],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()


def cached_sections(cache_key: str) -> dict[str, str] | None:
    with Session(engine) as session:
        hit = session.get(LlmResult, cache_key)
        return dict(hit.sections) if hit else None


async def run_task(
    req: RunRequest, client: anthropic.AsyncAnthropic, postprocess: PostProcess | None = None
) -> AsyncIterator[Event]:
    if req.task.json_schema is not None:
        async for e in _run_json(req, client, postprocess or (lambda d: d)):
            yield e
        return
    key = req.cache_key()
    if (hit := cached_sections(key)) is not None:
        yield {"event": "meta", "data": {"task": req.task.name, "model": req.model, "cached": True}}
        for name in req.task.sections:
            if name in hit:
                yield {"event": "section", "data": {"name": name, "delta": hit[name]}}
        yield {"event": "done", "data": {"model": req.model, "cached": True, "cost_usd": 0.0}}
        return

    yield {"event": "meta", "data": {"task": req.task.name, "model": req.model, "cached": False}}
    parser = TagStreamParser(req.task.sections)
    started = time.monotonic()
    try:
        async with _open_stream(req, client) as stream:
            async for text in stream.text_stream:
                for d in parser.feed(text):
                    yield {"event": "section", "data": {"name": d.name, "delta": d.text}}
            message = await stream.get_final_message()
    except anthropic.RateLimitError:
        yield {"event": "error", "data": {"message": "요청이 너무 많아요. 잠시 후 다시 시도해 주세요."}}
        return
    except anthropic.AuthenticationError:
        yield {"event": "error", "data": {"message": "API 키가 올바르지 않아요. backend/.env를 확인해 주세요."}}
        return
    except anthropic.APIStatusError as exc:
        yield {"event": "error", "data": {"message": f"LLM 호출에 실패했어요 ({exc.status_code})."}}
        return
    except anthropic.APIConnectionError:
        yield {"event": "error", "data": {"message": "LLM 서버에 연결하지 못했어요. 네트워크를 확인해 주세요."}}
        return

    for d in parser.finish():
        yield {"event": "section", "data": {"name": d.name, "delta": d.text}}

    usage = message.usage
    cache_read = usage.cache_read_input_tokens or 0
    cache_write = usage.cache_creation_input_tokens or 0
    cost = cost_usd(message.model, usage.input_tokens, usage.output_tokens, cache_read, cache_write)
    sections = parser.result()
    complete = message.stop_reason == "end_turn" and bool(sections)
    _record(req, message, key if complete else None, sections if complete else None, cost, started)

    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None) if message.stop_details else None
        yield {"event": "refused", "data": {"category": category, "message": _REFUSAL_MESSAGE}}
        return
    yield {
        "event": "done",
        "data": {
            "model": message.model,
            "cached": False,
            "cost_usd": cost,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "truncated": message.stop_reason == "max_tokens",
        },
    }


def _image(png: bytes) -> dict[str, Any]:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode()},
    }


def _open_stream(req: RunRequest, client: anthropic.AsyncAnthropic):
    content: list[dict[str, Any]] = []
    if req.image_png:
        content.append(_image(req.image_png))
    for label, png in req.labeled_images:
        if png:
            content.append({"type": "text", "text": f"표 이미지 [{label}]"})
            content.append(_image(png))
    content.append({"type": "text", "text": user_prompt(req.task, req.values)})
    params: dict[str, Any] = {
        "model": req.model,
        "max_tokens": max_tokens_for(req.task, req.detail),
        "system": system_prompt(req.background, req.level, req.detail, req.task.system_file),
        "messages": [{"role": "user", "content": content}],
    }
    output_config: dict[str, Any] = {}
    if req.task.json_schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": req.task.json_schema}
    if req.model == SONNET:
        # 사고(thinking) 노력은 작업마다 정한다: 해설은 low, 데이터 뼈대는 정확도를 위해 medium
        output_config["effort"] = req.task.effort
        return client.beta.messages.stream(
            **params, output_config=output_config, betas=[_FALLBACK_BETA], fallbacks="default"
        )
    if output_config:
        params["output_config"] = output_config
    return client.messages.stream(**params)


async def _run_json(req: RunRequest, client: anthropic.AsyncAnthropic, postprocess: PostProcess) -> AsyncIterator[Event]:
    """구조화 출력(JSON) 작업. 카드 형태라 조각 대신 진행 표시만 보내고, 끝나면 검증한 결과를 한 번에 보낸다."""
    key = req.cache_key()
    if (hit := cached_sections(key)) is not None:
        yield {"event": "meta", "data": {"task": req.task.name, "model": req.model, "cached": True}}
        yield {
            "event": "done",
            "data": {"model": req.model, "cached": True, "cost_usd": 0.0, "result": postprocess(json.loads(hit["json"]))},
        }
        return

    yield {"event": "meta", "data": {"task": req.task.name, "model": req.model, "cached": False}}
    started = time.monotonic()
    chunks: list[str] = []
    try:
        async with _open_stream(req, client) as stream:
            async for text in stream.text_stream:
                chunks.append(text)
                if len(chunks) % 20 == 0:
                    yield {"event": "progress", "data": {"chars": sum(map(len, chunks))}}
            message = await stream.get_final_message()
    except anthropic.APIError as exc:
        yield {"event": "error", "data": {"message": _api_error_message(exc)}}
        return

    usage = message.usage
    cost = cost_usd(
        message.model,
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_input_tokens or 0,
        usage.cache_creation_input_tokens or 0,
    )
    raw = "".join(chunks)
    parsed: dict[str, Any] | None = None
    if message.stop_reason == "end_turn":
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
    _record(req, message, key if parsed is not None else None, {"json": raw} if parsed is not None else None, cost, started)

    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None) if message.stop_details else None
        yield {"event": "refused", "data": {"category": category, "message": _REFUSAL_MESSAGE}}
        return
    if parsed is None:
        reason = "길이 제한으로 결과가 잘렸어요." if message.stop_reason == "max_tokens" else "결과 형식이 올바르지 않아요."
        yield {"event": "error", "data": {"message": f"{reason} 다시 시도해 주세요."}}
        return
    yield {
        "event": "done",
        "data": {
            "model": message.model,
            "cached": False,
            "cost_usd": cost,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "result": postprocess(parsed),
        },
    }


def _api_error_message(exc: anthropic.APIError) -> str:
    if isinstance(exc, anthropic.RateLimitError):
        return "요청이 너무 많아요. 잠시 후 다시 시도해 주세요."
    if isinstance(exc, anthropic.AuthenticationError):
        return "API 키가 올바르지 않아요. backend/.env를 확인해 주세요."
    if isinstance(exc, anthropic.APIConnectionError):
        return "LLM 서버에 연결하지 못했어요. 네트워크를 확인해 주세요."
    if isinstance(exc, anthropic.APIStatusError):
        return f"LLM 호출에 실패했어요 ({exc.status_code})."
    return "LLM 호출에 실패했어요."


def _record(
    req: RunRequest,
    message: Any,
    cache_key: str | None,
    sections: dict[str, str] | None,
    cost: float,
    started: float,
) -> None:
    usage = message.usage
    with Session(engine) as session:
        session.add(
            LlmCall(
                user_id=req.user_id,
                paper_id=req.paper_id,
                task=req.task.name,
                model=message.model,
                prompt_version=req.task.prompt_version,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
                cost_usd=cost,
                latency_ms=int((time.monotonic() - started) * 1000),
                stop_reason=message.stop_reason,
                cache_key=cache_key,
            )
        )
        if cache_key and sections and session.get(LlmResult, cache_key) is None:
            session.add(
                LlmResult(
                    cache_key=cache_key,
                    task=req.task.name,
                    model=req.model,
                    prompt_version=req.task.prompt_version,
                    sections=sections,
                )
            )
        session.commit()
