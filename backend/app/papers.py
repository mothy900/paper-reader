"""논문 파싱 결과를 DB에 반영한다. 업로드와 재파싱 스크립트가 함께 쓴다."""

from sqlmodel import Session, delete

from app.models import Block, Paper, PaperStatus, Sentence
from app.parsing import parse_pdf


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

    paper.title = parsed.title or paper.title
    paper.page_count = parsed.page_count
    paper.language = parsed.language
    paper.abstract = parsed.abstract
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
