from dataclasses import dataclass, field

from app.models import BlockType


@dataclass
class ParsedBlock:
    id: str
    seq: int
    page: int
    type: BlockType
    text: str
    bbox: tuple[float, float, float, float]
    section_id: str | None = None


@dataclass
class ParsedDocument:
    title: str | None
    page_count: int
    blocks: list[ParsedBlock] = field(default_factory=list)
