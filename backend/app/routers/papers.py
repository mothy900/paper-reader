from collections import defaultdict
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlmodel import Session, col, select

from app.config import settings
from app.db import get_session
from app.importing import Fetcher, SourceError, import_from
from app.models import Block, Paper, Sentence
from app.papers import create_paper
from app.schemas import BlockRead, ImportRequest, PaperRead
from app.storage import Storage, get_storage

router = APIRouter(prefix="/api/papers", tags=["papers"])

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


def get_fetcher() -> Fetcher:
    return Fetcher(max_bytes=settings.max_upload_mb * 1024 * 1024)


FetcherDep = Annotated[Fetcher, Depends(get_fetcher)]


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


@router.post(
    "",
    response_model=PaperRead,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "같은 파일이 이미 있어 기존 논문을 반환"}},
)
async def upload_paper(
    file: UploadFile, response: Response, session: SessionDep, storage: StorageDep
) -> Paper:
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file too large")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not a PDF file")

    paper, existed = create_paper(
        session,
        storage,
        data,
        fallback_title=PurePath(file.filename or "untitled.pdf").stem,
        source_type="upload",
    )
    if existed:
        response.status_code = status.HTTP_200_OK
    return paper


@router.post(
    "/import",
    response_model=PaperRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "같은 파일이 이미 있어 기존 논문을 반환"},
        422: {"description": "가져오기 실패 (detail에 사용자용 메시지)"},
    },
)
async def import_paper(
    body: ImportRequest,
    response: Response,
    session: SessionDep,
    storage: StorageDep,
    fetcher: FetcherDep,
) -> Paper:
    """웹 주소, arXiv ID, DOI로 논문을 가져온다."""
    try:
        imported = await import_from(body.url, fetcher)
    except SourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    paper, existed = create_paper(
        session,
        storage,
        imported.pdf,
        fallback_title=imported.source_url,
        source_type=imported.source_type,
        source_url=imported.source_url,
        meta=imported.meta,
    )
    if existed:
        response.status_code = status.HTTP_200_OK
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
    """화면에 보이는 블록만 문장 경계와 함께 반환한다 (숨은 텍스트 블록 제외)."""
    _get_paper(session, paper_id)
    blocks = session.exec(
        select(Block)
        .where(Block.paper_id == paper_id, col(Block.hidden).is_(False))
        .order_by(col(Block.seq))
    )
    sentences: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for s in session.exec(
        select(Sentence)
        .where(Sentence.paper_id == paper_id)
        .order_by(col(Sentence.block_id), col(Sentence.idx))
    ):
        sentences[s.block_id].append((s.start, s.end))
    return [
        BlockRead(
            id=b.id,
            seq=b.seq,
            page=b.page,
            type=b.type,
            text=b.text,
            bbox=(b.x0, b.y0, b.x1, b.y1),
            section_id=b.section_id,
            level=b.level,
            sentences=sentences.get(b.id, []),
        )
        for b in blocks
    ]


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(paper_id: str, session: SessionDep, storage: StorageDep) -> None:
    paper = _get_paper(session, paper_id)
    storage.delete(paper.file_key)
    session.delete(paper)
    session.commit()
