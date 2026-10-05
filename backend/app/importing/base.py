from dataclasses import dataclass, field


class SourceError(Exception):
    """사용자에게 그대로 보여줄 수 있는 가져오기 실패 사유."""


@dataclass
class PaperMeta:
    """출처(arXiv API, 논문 페이지 메타 태그 등)가 알려준 정보. 파서 추측보다 우선한다."""

    source: str  # "arxiv" | "citation_meta" | "semantic_scholar"
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
