"""논문 생성과 파싱 결과 반영. 업로드·주소 가져오기·재파싱 스크립트가 함께 쓴다."""

import hashlib

from sqlmodel import Session, delete, select

from app.config import settings
from app.importing import PaperMeta
from app.models import Block, Paper, PaperStatus, Sentence
from app.parsing import parse_pdf
from app.storage import Storage


def create_paper(
    session: Session,
    storage: Storage,
    data: bytes,
    *,
    fallback_title: str,
    source_type: str,
    source_url: str | None = None,
    meta: PaperMeta | None = None,
) -> tuple[Paper, bool]:
    """PDF로 논문을 만든다. 같은 파일이 이미 있으면 (기존 논문, True)를 돌려준다."""
    sha256 = hashlib.sha256(data).hexdigest()
    existing = session.exec(
        select(Paper).where(Paper.user_id == settings.default_user_id, Paper.sha256 == sha256)
    ).first()
    if existing:
        return existing, True

    paper = Paper(
        user_id=settings.default_user_id,
        title=fallback_title,
        source_type=source_type,
        source_url=source_url,
        file_key="",
        sha256=sha256,
    )
    if meta:
        apply_meta(paper, meta)
    paper.file_key = f"{paper.user_id}/{paper.id}.pdf"
    storage.save(paper.file_key, data)
    session.add(paper)
    session.flush()  # 블록의 외래키보다 paper 행이 먼저 들어가야 한다

    # PyMuPDF 파싱은 수 초 이내라 동기로 처리. 무거운 파서로 바꾸면 백그라운드 작업으로 옮긴다.
    apply_parse(session, paper, data)
    session.commit()
    session.refresh(paper)
    return paper, False


def apply_meta(paper: Paper, meta: PaperMeta) -> None:
    paper.title = meta.title or paper.title
    paper.authors = meta.authors
    paper.year = meta.year
    paper.abstract = meta.abstract
    paper.arxiv_id = meta.arxiv_id
    paper.doi = meta.doi
    paper.metadata_source = meta.source


def apply_parse(session: Session, paper: Paper, data: bytes) -> None:
    """기존 블록·문장을 지우고 다시 파싱해 저장한다. 커밋은 호출하는 쪽에서 한다."""
    session.exec(delete(Sentence).where(Sentence.paper_id == paper.id))
    session.exec(delete(Block).where(Block.paper_id == paper.id))

    try:
        parsed = parse_pdf(data)
    except Exception as exc:  # noqa: BLE001 - 파싱 실패도 논문 레코드로 남긴다
        paper.status = PaperStatus.failed
        paper.error = str(exc)
        return

    if paper.metadata_source:
        # 출처가 알려준 제목·초록이 파서 추측보다 정확하다
        paper.abstract = paper.abstract or parsed.abstract
    else:
        paper.title = parsed.title or paper.title
        paper.abstract = parsed.abstract
    paper.page_count = parsed.page_count
    paper.language = parsed.language
    paper.hidden_text_count = parsed.hidden_text_count
    paper.parser_version = parsed.parser_version
    paper.status = PaperStatus.ready
    paper.error = None
    for b in parsed.blocks:
        session.add(
            Block(
                paper_id=paper.id,
                id=b.id,
                seq=b.seq,
                page=b.page,
                type=b.type,
                text=b.text,
                x0=b.bbox[0],
                y0=b.bbox[1],
                x1=b.bbox[2],
                y1=b.bbox[3],
                section_id=b.section_id,
                level=b.level,
                hidden=b.hidden,
            )
        )
        session.add_all(
            Sentence(paper_id=paper.id, block_id=b.id, idx=i, start=start, end=end)
            for i, (start, end) in enumerate(b.sentences)
        )
