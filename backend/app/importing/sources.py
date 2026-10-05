"""출처별 파서: arXiv ID·DOI 인식, arXiv API, 논문 페이지 메타 태그, Semantic Scholar."""

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlsplit

from app.importing.base import PaperMeta
from app.text import normalize

# 2007년 이후: 1706.03762, 2401.00001v2 / 이전: hep-th/9901001, math.GT/0309136
_ARXIV_NEW = r"\d{4}\.\d{4,5}(?:v\d+)?"
_ARXIV_OLD = r"[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?"
_ARXIV_ID = re.compile(rf"^(?:arxiv:\s*)?({_ARXIV_NEW}|{_ARXIV_OLD})$", re.IGNORECASE)
_ARXIV_URL_PATH = re.compile(rf"^/(?:abs|pdf|html)/({_ARXIV_NEW}|{_ARXIV_OLD})(?:\.pdf)?/?$")
_DOI = re.compile(r"^(?:doi:\s*)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
_ATOM = {"a": "http://www.w3.org/2005/Atom"}


def parse_arxiv_id(text: str) -> str | None:
    """arXiv ID, arxiv.org의 abs/pdf/html 주소에서 ID를 뽑는다."""
    text = text.strip()
    if m := _ARXIV_ID.match(text):
        return m.group(1)
    parts = urlsplit(text)
    if parts.hostname in ("arxiv.org", "www.arxiv.org", "export.arxiv.org"):
        if m := _ARXIV_URL_PATH.match(parts.path):
            return m.group(1)
    return None


def parse_doi(text: str) -> str | None:
    """DOI 문자열 또는 doi.org 주소에서 DOI를 뽑는다."""
    text = text.strip()
    parts = urlsplit(text)
    if parts.hostname in ("doi.org", "dx.doi.org", "www.doi.org"):
        text = unquote(parts.path.lstrip("/"))
    if m := _DOI.match(text):
        return m.group(1).rstrip(".,;")
    return None


def arxiv_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}"


def arxiv_api_url(arxiv_id: str) -> str:
    return f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id)}"


def parse_arxiv_atom(xml: str, arxiv_id: str) -> PaperMeta:
    entry = ET.fromstring(xml).find("a:entry", _ATOM)
    meta = PaperMeta(source="arxiv", arxiv_id=arxiv_id)
    if entry is None or entry.find("a:title", _ATOM) is None:
        return meta
    text = lambda tag: normalize(entry.findtext(tag, default="", namespaces=_ATOM)) or None  # noqa: E731
    meta.title = text("a:title")
    meta.abstract = text("a:summary")
    meta.authors = [normalize(a.findtext("a:name", "", _ATOM)) for a in entry.findall("a:author", _ATOM)]
    if published := text("a:published"):
        meta.year = int(published[:4])
    meta.doi = entry.findtext("{http://arxiv.org/schemas/atom}doi")
    return meta


class _CitationMetaParser(HTMLParser):
    """구글 스칼라용 citation_* 메타 태그를 모은다. 대부분의 학술 사이트가 제공한다."""

    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        a = dict(attrs)
        name = (a.get("name") or a.get("property") or "").lower()
        if name.startswith("citation_") and a.get("content"):
            self.values.setdefault(name, []).append(a["content"].strip())


def parse_citation_meta(html: str, base_url: str) -> tuple[str | None, PaperMeta]:
    """논문 페이지에서 PDF 주소와 메타데이터를 찾는다."""
    parser = _CitationMetaParser()
    parser.feed(html)
    v = parser.values
    first = lambda key: normalize(v[key][0]) if v.get(key) else None  # noqa: E731

    pdf_url = urljoin(base_url, v["citation_pdf_url"][0]) if v.get("citation_pdf_url") else None
    meta = PaperMeta(
        source="citation_meta",
        title=first("citation_title"),
        authors=[normalize(a) for a in v.get("citation_author", [])],
        abstract=first("citation_abstract"),
        doi=first("citation_doi"),
        arxiv_id=first("citation_arxiv_id"),
    )
    for key in ("citation_publication_date", "citation_date", "citation_online_date", "citation_year"):
        if (date := first(key)) and (m := re.search(r"(19|20)\d{2}", date)):
            meta.year = int(m.group(0))
            break
    return pdf_url, meta


def semantic_scholar_url(doi: str) -> str:
    fields = "title,authors,year,abstract,openAccessPdf,externalIds"
    return f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='/')}?fields={fields}"


def parse_semantic_scholar(data: dict, doi: str) -> tuple[str | None, PaperMeta]:
    ids = data.get("externalIds") or {}
    meta = PaperMeta(
        source="semantic_scholar",
        title=data.get("title"),
        authors=[a["name"] for a in data.get("authors") or [] if a.get("name")],
        year=data.get("year"),
        abstract=data.get("abstract"),
        doi=doi,
        arxiv_id=ids.get("ArXiv"),
    )
    pdf = (data.get("openAccessPdf") or {}).get("url") or None
    return pdf, meta
