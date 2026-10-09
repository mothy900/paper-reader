from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


# 제약 조건에 이름을 붙여야 Alembic이 나중에 지우거나 바꿀 수 있다
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


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
    equation = "equation"
    table = "table"


class Paper(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "sha256"),)

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(index=True)
    title: str
    source_type: str  # "upload" | "arxiv" | "doi" | "url"
    source_url: str | None = None
    file_key: str
    sha256: str | None = None  # 같은 파일 중복 업로드 방지
    page_count: int = 0
    language: str = Field(default="en", sa_column_kwargs={"server_default": "en"})
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))
    year: int | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    # 제목·저자·초록을 출처에서 가져왔으면 그 출처 ("arxiv" | "citation_meta" | "semantic_scholar").
    # 이 값이 있으면 재파싱해도 제목·초록을 파서 추측으로 덮어쓰지 않는다.
    metadata_source: str | None = None
    # 숨은 텍스트가 발견된 블록 수
    hidden_text_count: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    parser_version: str | None = None
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
    level: int | None = None  # heading일 때 1~3
    # 사람 눈에 안 보이는 텍스트. 화면·LLM 입력에서 제외
    hidden: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})


class Sentence(SQLModel, table=True):
    """블록 안의 문장. text[start:end]가 문장이다 (Block.text는 정규화된 텍스트)."""

    paper_id: str = Field(foreign_key="paper.id", primary_key=True, ondelete="CASCADE")
    block_id: str = Field(primary_key=True)
    idx: int = Field(primary_key=True)
    start: int
    end: int


class UserProfile(SQLModel, table=True):
    """설명을 사용자 수준에 맞추기 위한 정보. 모든 해설 프롬프트에 들어간다."""

    user_id: str = Field(primary_key=True)
    background: str = ""  # 자유 텍스트, 예: "개발자, 선형대수 기초, ML 입문"
    level: str = "beginner"  # beginner | intermediate | expert
    updated_at: datetime = Field(default_factory=_now)


class LlmCall(SQLModel, table=True):
    """LLM 호출 기록. 비용을 화면에 보여주고 프롬프트를 조정할 때 근거로 쓴다."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    paper_id: str | None = Field(default=None, index=True)
    task: str
    model: str  # 실제로 응답한 모델 (대체 모델로 넘어갔으면 그 모델)
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    stop_reason: str | None = None
    cache_key: str | None = None
    created_at: datetime = Field(default_factory=_now)


class LlmResult(SQLModel, table=True):
    """LLM 결과 캐시. 같은 입력이면 다시 호출하지 않는다."""

    cache_key: str = Field(primary_key=True)
    task: str
    model: str
    prompt_version: str
    sections: dict[str, str] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=_now)


class ExplainHistory(SQLModel, table=True):
    """논문별 해설 기록. 다시 열면 캐시된 결과를 보여준다 (나중에 용어장의 재료)."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    paper_id: str = Field(foreign_key="paper.id", index=True, ondelete="CASCADE")
    task: str
    detail: str  # basic | deep
    focus: dict = Field(sa_column=Column(JSON, nullable=False))
    label: str  # 목록에 보여줄 짧은 텍스트
    cache_key: str
    created_at: datetime = Field(default_factory=_now)
