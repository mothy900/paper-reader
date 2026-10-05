from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class PaperStatus(StrEnum):
    parsing = "parsing"
    ready = "ready"
    failed = "failed"


class BlockType(StrEnum):
    heading = "heading"
    paragraph = "paragraph"
    caption = "caption"
    figure = "figure"


class Paper(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(index=True)
    title: str
    source_type: str  # "upload" | "arxiv" | "doi" | "url"
    source_url: str | None = None
    file_key: str
    page_count: int = 0
    status: PaperStatus = PaperStatus.parsing
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)


class Block(SQLModel, table=True):
    """논문을 구성하는 최소 단위. 모든 LLM 기능은 block id를 근거로 삼는다."""

    paper_id: str = Field(foreign_key="paper.id", primary_key=True, ondelete="CASCADE")
    id: str = Field(primary_key=True)  # 예: "p3-12" (3페이지 12번째 블록)
    seq: int = Field(index=True)  # 문서 전체 읽기 순서
    page: int  # 1부터 시작
    type: BlockType
    text: str
    # PDF 좌표(pt), 페이지 왼쪽 위 원점
    x0: float
    y0: float
    x1: float
    y1: float
    section_id: str | None = None  # 이 블록이 속한 heading 블록의 id
