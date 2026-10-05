from dataclasses import dataclass, field

from app.models import BlockType
from app.text.processor import Span


@dataclass
class ParsedBlock:
    id: str
    seq: int
    page: int
    type: BlockType
    text: str
    bbox: tuple[float, float, float, float]
    section_id: str | None = None
    level: int | None = None  # heading일 때만 1~3
    hidden: bool = False
    sentences: list[Span] = field(default_factory=list)


@dataclass
class ParsedDocument:
    title: str | None
    page_count: int
    parser_version: str
    language: str = "en"
    abstract: str | None = None
    hidden_text_count: int = 0
    blocks: list[ParsedBlock] = field(default_factory=list)
