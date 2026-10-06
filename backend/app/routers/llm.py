import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, SQLModel, col, select

from app.config import settings
from app.db import get_session
from app.llm.client import get_llm_client
from app.llm.context import Focus, FocusRange, prepare_explain, prepare_translate
from app.llm.runner import Event, RunRequest, run_task
from app.llm.tasks import TRANSLATE, Detail
from app.models import ExplainHistory, LlmCall, Paper, UserProfile
from app.storage import Storage, get_storage

router = APIRouter(prefix="/api", tags=["llm"])

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
ClientDep = Annotated[anthropic.AsyncAnthropic, Depends(get_llm_client)]

HISTORY_LIMIT = 50


class RangeIn(SQLModel):
    block_id: str
    start: int
    end: int


class FocusIn(SQLModel):
    source: Literal["selection", "block"]
    text: str
    block_ids: list[str]
    ranges: list[RangeIn]
    sentence_ids: list[str] = []


class ExplainRequest(SQLModel):
    focus: FocusIn
    detail: Detail = Detail.basic


class TranslateRequest(SQLModel):
    block_id: str
    detail: Detail = Detail.basic


class ProfileIO(SQLModel):
    background: str
    level: Literal["beginner", "intermediate", "expert"]


class UsageOut(SQLModel):
    cost_usd: float
    calls: int


class HistoryOut(SQLModel):
    id: int
    task: str
    detail: str
    label: str
    focus: dict


def _paper(session: Session, paper_id: str) -> Paper:
    paper = session.get(Paper, paper_id)
    if paper is None or paper.user_id != settings.default_user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")
    return paper


def _profile(session: Session) -> UserProfile:
    return session.get(UserProfile, settings.default_user_id) or UserProfile(user_id=settings.default_user_id)


def _sse(events: AsyncIterator[Event]) -> StreamingResponse:
    async def body() -> AsyncIterator[str]:
        async for e in events:
            yield f"event: {e['event']}\ndata: {json.dumps(e['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(
        body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/papers/{paper_id}/explain")
def explain(
    paper_id: str, body: ExplainRequest, session: SessionDep, storage: StorageDep, client: ClientDep
) -> StreamingResponse:
    """포커스(드래그한 문구·클릭한 문단·수식)를 해설한다. SSE로 섹션별 스트리밍."""
    paper = _paper(session, paper_id)
    focus = Focus(
        source=body.focus.source,
        text=body.focus.text,
        block_ids=body.focus.block_ids,
        ranges=[FocusRange(r.block_id, r.start, r.end) for r in body.focus.ranges],
        sentence_ids=body.focus.sentence_ids,
    )
    try:
        prepared = prepare_explain(session, storage, paper, focus)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    profile = _profile(session)
    req = RunRequest(
        task=prepared.task,
        detail=body.detail,
        values=prepared.values,
        background=profile.background,
        level=profile.level,
        user_id=settings.default_user_id,
        paper_id=paper.id,
        image_png=prepared.image_png,
    )
    _remember(session, paper.id, req, body)
    return _sse(run_task(req, client))


@router.post("/papers/{paper_id}/translate")
def translate(paper_id: str, body: TranslateRequest, session: SessionDep, client: ClientDep) -> StreamingResponse:
    """문단 하나를 번역한다. SSE로 스트리밍."""
    paper = _paper(session, paper_id)
    try:
        values = prepare_translate(session, paper, body.block_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    profile = _profile(session)
    req = RunRequest(
        task=TRANSLATE,
        detail=body.detail,
        values=values,
        background=profile.background,
        level=profile.level,
        user_id=settings.default_user_id,
        paper_id=paper.id,
    )
    return _sse(run_task(req, client))


@router.get("/papers/{paper_id}/usage", response_model=UsageOut)
def paper_usage(paper_id: str, session: SessionDep) -> UsageOut:
    _paper(session, paper_id)
    cost, calls = session.exec(
        select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0), func.count(col(LlmCall.id))).where(
            LlmCall.paper_id == paper_id, LlmCall.user_id == settings.default_user_id
        )
    ).one()
    return UsageOut(cost_usd=round(cost, 6), calls=calls)


@router.get("/papers/{paper_id}/history", response_model=list[HistoryOut])
def paper_history(paper_id: str, session: SessionDep) -> list[ExplainHistory]:
    _paper(session, paper_id)
    return list(
        session.exec(
            select(ExplainHistory)
            .where(ExplainHistory.paper_id == paper_id, ExplainHistory.user_id == settings.default_user_id)
            .order_by(col(ExplainHistory.id).desc())
            .limit(HISTORY_LIMIT)
        )
    )


@router.get("/profile", response_model=ProfileIO | None)
def get_profile(session: SessionDep) -> UserProfile | None:
    """아직 입력하지 않았으면 null (프론트가 첫 실행 안내를 띄운다)."""
    return session.get(UserProfile, settings.default_user_id)


@router.put("/profile", response_model=ProfileIO)
def put_profile(body: ProfileIO, session: SessionDep) -> UserProfile:
    profile = _profile(session)
    profile.background = body.background.strip()
    profile.level = body.level
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def _remember(session: Session, paper_id: str, req: RunRequest, body: ExplainRequest) -> None:
    """해설 기록을 남긴다. 직전 기록과 같으면(다시 연 경우) 쌓지 않는다."""
    key = req.cache_key()
    last = session.exec(
        select(ExplainHistory)
        .where(ExplainHistory.paper_id == paper_id, ExplainHistory.user_id == settings.default_user_id)
        .order_by(col(ExplainHistory.id).desc())
    ).first()
    if last and last.cache_key == key:
        return
    label = " ".join(body.focus.text.split())
    session.add(
        ExplainHistory(
            user_id=settings.default_user_id,
            paper_id=paper_id,
            task=req.task.name,
            detail=body.detail.value,
            focus=body.focus.model_dump(),
            label=label[:80] + ("…" if len(label) > 80 else ""),
            cache_key=key,
        )
    )
    session.commit()
