"""입력(주소·arXiv ID·DOI)을 PDF와 메타데이터로 바꾼다."""

import json
from dataclasses import dataclass

from app.importing.base import PaperMeta, SourceError
from app.importing.fetch import Fetcher
from app.importing.sources import (
    arxiv_api_url,
    arxiv_pdf_url,
    parse_arxiv_atom,
    parse_arxiv_id,
    parse_citation_meta,
    parse_doi,
    parse_semantic_scholar,
    semantic_scholar_url,
)

_PAYWALL_HINT = "무료로 공개된 PDF를 찾지 못했어요. 구독이 필요한 논문이면 PDF를 직접 올려 주세요."
_NO_PDF_HINT = (
    "이 페이지에서 논문 PDF를 찾지 못했어요. PDF 링크나 arXiv 주소를 넣거나, 파일을 직접 올려 주세요."
)


@dataclass
class ImportedPaper:
    pdf: bytes
    source_type: str  # "arxiv" | "doi" | "url"
    source_url: str
    meta: PaperMeta | None


async def import_from(text: str, fetcher: Fetcher) -> ImportedPaper:
    text = text.strip()
    if not text:
        raise SourceError("주소를 입력해 주세요.")
    if arxiv_id := parse_arxiv_id(text):
        return await _from_arxiv(arxiv_id, fetcher)
    if doi := parse_doi(text):
        return await _from_doi(doi, fetcher)
    if text.startswith(("http://", "https://")):
        return await _from_url(text, fetcher)
    raise SourceError("웹 주소, arXiv ID(예: 1706.03762), DOI(예: 10.18653/v1/N19-1423) 중 하나를 입력해 주세요.")


async def _from_arxiv(arxiv_id: str, fetcher: Fetcher) -> ImportedPaper:
    pdf = await fetcher.get(arxiv_pdf_url(arxiv_id), accept="application/pdf")
    if not pdf.is_pdf:
        raise SourceError(f"arXiv에서 PDF를 받지 못했어요: {arxiv_id}")
    try:
        atom = await fetcher.get(arxiv_api_url(arxiv_id), accept="application/atom+xml")
        meta = parse_arxiv_atom(atom.text, arxiv_id)
    except Exception:  # noqa: BLE001 - 메타데이터가 없어도 PDF 파싱 결과로 충분하다
        meta = PaperMeta(source="arxiv", arxiv_id=arxiv_id)
    return ImportedPaper(pdf.body, "arxiv", f"https://arxiv.org/abs/{arxiv_id}", meta)


async def _from_doi(doi: str, fetcher: Fetcher) -> ImportedPaper:
    # 1) doi.org가 보내주는 논문 페이지의 메타 태그
    try:
        imported = await _from_url(f"https://doi.org/{doi}", fetcher, source_type="doi")
    except SourceError:
        imported = None
    if imported:
        if imported.meta:
            imported.meta.doi = imported.meta.doi or doi
        return imported

    # 2) Semantic Scholar의 공개 PDF (arXiv 버전이 있으면 그쪽이 더 안정적)
    try:
        res = await fetcher.get(semantic_scholar_url(doi), accept="application/json")
        pdf_url, meta = parse_semantic_scholar(json.loads(res.body), doi)
    except (SourceError, ValueError):
        raise SourceError(_PAYWALL_HINT) from None
    if meta.arxiv_id:
        imported = await _from_arxiv(meta.arxiv_id, fetcher)
        if imported.meta:
            imported.meta.doi = doi
        return imported
    if not pdf_url:
        raise SourceError(_PAYWALL_HINT)
    pdf = await fetcher.get(pdf_url, accept="application/pdf")
    if not pdf.is_pdf:
        raise SourceError(_PAYWALL_HINT)
    return ImportedPaper(pdf.body, "doi", f"https://doi.org/{doi}", meta)


async def _from_url(url: str, fetcher: Fetcher, source_type: str = "url") -> ImportedPaper:
    res = await fetcher.get(url, accept="application/pdf,text/html;q=0.9,*/*;q=0.5")
    if res.is_pdf:
        return ImportedPaper(res.body, source_type, url, None)
    if "html" not in res.content_type:
        raise SourceError("PDF나 논문 페이지가 아니에요.")

    # 리다이렉트 끝에 arXiv 페이지가 있으면 arXiv로 처리
    if arxiv_id := parse_arxiv_id(res.url):
        return await _from_arxiv(arxiv_id, fetcher)

    pdf_url, meta = parse_citation_meta(res.text, res.url)
    if not pdf_url:
        if meta.arxiv_id:
            return await _from_arxiv(meta.arxiv_id, fetcher)
        raise SourceError(_PAYWALL_HINT if meta.title else _NO_PDF_HINT)
    pdf = await fetcher.get(pdf_url, accept="application/pdf")
    if not pdf.is_pdf:
        raise SourceError(_PAYWALL_HINT)
    has_meta = meta.title or meta.authors
    return ImportedPaper(pdf.body, source_type, url, meta if has_meta else None)
