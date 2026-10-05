from datetime import datetime

from sqlmodel import SQLModel

from app.models import BlockType, PaperStatus


class PaperRead(SQLModel):
    id: str
    title: str
    source_type: str
    source_url: str | None
    authors: list[str]
    year: int | None
    arxiv_id: str | None
    doi: str | None
    page_count: int
    language: str
    abstract: str | None
    hidden_text_count: int
    status: PaperStatus
    error: str | None
    created_at: datetime


class BlockRead(SQLModel):
    id: str
    seq: int
    page: int
    type: BlockType
    text: str
    bbox: tuple[float, float, float, float]
    section_id: str | None
    level: int | None
    sentences: list[tuple[int, int]]


class ImportRequest(SQLModel):
    url: str  # 웹 주소, arXiv ID, DOI
