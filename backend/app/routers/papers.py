from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlmodel import Session, col, select

from app.config import settings
from app.db import get_session
from app.models import Block, Paper, PaperStatus
from app.parsing import parse_pdf
from app.schemas import BlockRead, PaperRead
from app.storage import Storage, get_storage

router = APIRouter(prefix="/api/papers", tags=["papers"])

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


def _get_paper(session: Session, paper_id: str) -> Paper:
    paper = session.get(Paper, paper_id)
    if paper is None or paper.user_id != settings.default_user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")
    return paper


@router.get("", response_model=list[PaperRead])
def list_papers(session: SessionDep) -> list[Paper]:
    stmt = (
        select(Paper)
        .where(Paper.user_id == settings.default_user_id)
        .order_by(col(Paper.created_at).desc())
    )
    return list(session.exec(stmt))


@router.post("", response_model=PaperRead, status_code=status.HTTP_201_CREATED)
async def upload_paper(file: UploadFile, session: SessionDep, storage: StorageDep) -> Paper:
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file too large")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not a PDF file")

    fallback_title = PurePath(file.filename or "untitled.pdf").stem
    paper = Paper(
        user_id=settings.default_user_id,
        title=fallback_title,
        source_type="upload",
        file_key="",
    )
    paper.file_key = f"{paper.user_id}/{paper.id}.pdf"
    storage.save(paper.file_key, data)
    session.add(paper)
    session.flush()  # 블록의 외래키보다 paper 행이 먼저 들어가야 한다

    # PyMuPDF 파싱은 수 초 이내라 동기로 처리. 무거운 파서로 바꾸면 백그라운드 작업으로 옮긴다.
    try:
        parsed = parse_pdf(data)
    except Exception as exc:  # noqa: BLE001 - 파싱 실패도 논문 레코드로 남긴다
        paper.status = PaperStatus.failed
        paper.error = str(exc)
    else:
        paper.title = parsed.title or fallback_title
        paper.page_count = parsed.page_count
        paper.status = PaperStatus.ready
        session.add_all(
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
            )
            for b in parsed.blocks
        )

    session.commit()
    session.refresh(paper)
    return paper


@router.get("/{paper_id}", response_model=PaperRead)
def get_paper(paper_id: str, session: SessionDep) -> Paper:
    return _get_paper(session, paper_id)


@router.get("/{paper_id}/file")
def get_paper_file(paper_id: str, session: SessionDep, storage: StorageDep) -> Response:
    paper = _get_paper(session, paper_id)
    return Response(storage.load(paper.file_key), media_type="application/pdf")


@router.get("/{paper_id}/blocks", response_model=list[BlockRead])
def get_paper_blocks(paper_id: str, session: SessionDep) -> list[BlockRead]:
    _get_paper(session, paper_id)
    blocks = session.exec(select(Block).where(Block.paper_id == paper_id).order_by(col(Block.seq)))
    return [
        BlockRead(
            id=b.id,
            seq=b.seq,
            page=b.page,
            type=b.type,
            text=b.text,
            bbox=(b.x0, b.y0, b.x1, b.y1),
            section_id=b.section_id,
        )
        for b in blocks
    ]


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(paper_id: str, session: SessionDep, storage: StorageDep) -> None:
    paper = _get_paper(session, paper_id)
    storage.delete(paper.file_key)
    session.delete(paper)
    session.commit()
