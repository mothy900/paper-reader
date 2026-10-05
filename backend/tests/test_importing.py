import json

import httpx
import pytest

from app.importing import Fetcher, SourceError, import_from
from app.importing.sources import parse_arxiv_id, parse_citation_meta, parse_doi
from tests.conftest import make_paper_pdf

PDF = make_paper_pdf(hidden=False)

ARXIV_ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All
      You Need</title>
    <summary> The dominant sequence transduction models... </summary>
    <published>2017-06-12T17:57:34Z</published>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
  </entry>
</feed>"""

LANDING = """<html><head>
<meta name="citation_title" content="BERT: Pre-training of Deep Bidirectional Transformers">
<meta name="citation_author" content="Devlin, Jacob">
<meta name="citation_author" content="Chang, Ming-Wei">
<meta name="citation_publication_date" content="2019/6">
<meta name="citation_doi" content="10.18653/v1/N19-1423">
<meta name="citation_pdf_url" content="/N19-1423.pdf">
</head><body>paper</body></html>"""

PAYWALL = """<html><head>
<meta name="citation_title" content="A Paywalled Paper">
</head></html>"""


def make_fetcher(routes: dict[str, httpx.Response], resolver=lambda host: ["93.184.216.34"], **kw) -> Fetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url not in routes:
            return httpx.Response(404)
        return routes[url]

    return Fetcher(httpx.AsyncClient(transport=httpx.MockTransport(handler)), resolver=resolver, **kw)


def pdf_response() -> httpx.Response:
    return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})


def html_response(html: str) -> httpx.Response:
    return httpx.Response(200, text=html, headers={"content-type": "text/html; charset=utf-8"})


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1706.03762", "1706.03762"),
        ("arXiv:1706.03762v7", "1706.03762v7"),
        ("https://arxiv.org/abs/1706.03762", "1706.03762"),
        ("https://arxiv.org/pdf/1706.03762v2", "1706.03762v2"),
        ("https://arxiv.org/pdf/1706.03762.pdf", "1706.03762"),
        ("https://arxiv.org/html/2401.00001v1", "2401.00001v1"),
        ("https://arxiv.org/abs/hep-th/9901001", "hep-th/9901001"),
        ("https://example.com/abs/1706.03762", None),
        ("10.18653/v1/N19-1423", None),
    ],
)
def test_parse_arxiv_id(text: str, expected: str | None) -> None:
    assert parse_arxiv_id(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10.18653/v1/N19-1423", "10.18653/v1/N19-1423"),
        ("doi:10.1145/3292500.3330701", "10.1145/3292500.3330701"),
        ("https://doi.org/10.1038/nature14539", "10.1038/nature14539"),
        ("https://dx.doi.org/10.1038%2Fnature14539", "10.1038/nature14539"),
        ("https://example.com/10.1038/x", None),
        ("1706.03762", None),
    ],
)
def test_parse_doi(text: str, expected: str | None) -> None:
    assert parse_doi(text) == expected


def test_parse_citation_meta_resolves_relative_pdf_url() -> None:
    pdf_url, meta = parse_citation_meta(LANDING, "https://aclanthology.org/N19-1423/")

    assert pdf_url == "https://aclanthology.org/N19-1423.pdf"
    assert meta.title == "BERT: Pre-training of Deep Bidirectional Transformers"
    assert meta.authors == ["Devlin, Jacob", "Chang, Ming-Wei"]
    assert meta.year == 2019
    assert meta.doi == "10.18653/v1/N19-1423"


async def test_import_arxiv_uses_api_metadata() -> None:
    fetcher = make_fetcher(
        {
            "https://arxiv.org/pdf/1706.03762": pdf_response(),
            "https://export.arxiv.org/api/query?id_list=1706.03762": httpx.Response(200, text=ARXIV_ATOM),
        }
    )
    imported = await import_from("https://arxiv.org/abs/1706.03762", fetcher)

    assert imported.pdf == PDF
    assert imported.source_type == "arxiv"
    assert imported.meta.title == "Attention Is All You Need"
    assert imported.meta.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert imported.meta.year == 2017
    assert imported.meta.abstract == "The dominant sequence transduction models..."


async def test_import_arxiv_survives_metadata_failure() -> None:
    fetcher = make_fetcher({"https://arxiv.org/pdf/1706.03762": pdf_response()})
    imported = await import_from("1706.03762", fetcher)

    assert imported.pdf == PDF
    assert imported.meta.title is None


async def test_import_direct_pdf_link() -> None:
    fetcher = make_fetcher({"https://example.com/paper.pdf": pdf_response()})
    imported = await import_from("https://example.com/paper.pdf", fetcher)

    assert imported.pdf == PDF
    assert imported.source_type == "url"
    assert imported.meta is None


async def test_import_landing_page_follows_citation_pdf_url() -> None:
    fetcher = make_fetcher(
        {
            "https://aclanthology.org/N19-1423/": html_response(LANDING),
            "https://aclanthology.org/N19-1423.pdf": pdf_response(),
        }
    )
    imported = await import_from("https://aclanthology.org/N19-1423/", fetcher)

    assert imported.pdf == PDF
    assert imported.meta.authors == ["Devlin, Jacob", "Chang, Ming-Wei"]


async def test_import_doi_follows_redirect_to_landing_page() -> None:
    fetcher = make_fetcher(
        {
            "https://doi.org/10.18653/v1/N19-1423": httpx.Response(
                302, headers={"location": "https://aclanthology.org/N19-1423/"}
            ),
            "https://aclanthology.org/N19-1423/": html_response(LANDING),
            "https://aclanthology.org/N19-1423.pdf": pdf_response(),
        }
    )
    imported = await import_from("10.18653/v1/N19-1423", fetcher)

    assert imported.source_type == "doi"
    assert imported.meta.doi == "10.18653/v1/N19-1423"


async def test_import_doi_falls_back_to_semantic_scholar_arxiv() -> None:
    s2 = {"title": "Deep learning", "authors": [], "externalIds": {"ArXiv": "1706.03762"}, "openAccessPdf": None}
    fetcher = make_fetcher(
        {
            "https://doi.org/10.1038/nature14539": html_response(PAYWALL),
            "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature14539"
            "?fields=title,authors,year,abstract,openAccessPdf,externalIds": httpx.Response(200, json=s2),
            "https://arxiv.org/pdf/1706.03762": pdf_response(),
        }
    )
    imported = await import_from("https://doi.org/10.1038/nature14539", fetcher)

    assert imported.source_type == "arxiv"
    assert imported.meta.doi == "10.1038/nature14539"


async def test_paywalled_paper_explains_what_to_do() -> None:
    fetcher = make_fetcher({"https://publisher.example/paper": html_response(PAYWALL)})

    with pytest.raises(SourceError, match="PDF를 직접 올려"):
        await import_from("https://publisher.example/paper", fetcher)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1"])
async def test_blocks_private_network(address: str) -> None:
    fetcher = make_fetcher({"http://internal.example/x.pdf": pdf_response()}, resolver=lambda host: [address])

    with pytest.raises(SourceError, match="내부망"):
        await import_from("http://internal.example/x.pdf", fetcher)


async def test_blocks_redirect_into_private_network() -> None:
    def resolver(host: str) -> list[str]:
        return ["127.0.0.1"] if host == "localhost" else ["93.184.216.34"]

    fetcher = make_fetcher(
        {"https://example.com/go": httpx.Response(302, headers={"location": "http://localhost:8000/secret"})},
        resolver=resolver,
    )
    with pytest.raises(SourceError, match="내부망"):
        await import_from("https://example.com/go", fetcher)


async def test_rejects_non_http_scheme_and_garbage() -> None:
    fetcher = make_fetcher({})
    with pytest.raises(SourceError):
        await import_from("file:///etc/passwd", fetcher)
    with pytest.raises(SourceError, match="arXiv ID"):
        await import_from("just some words", fetcher)


async def test_enforces_size_limit() -> None:
    fetcher = make_fetcher({"https://example.com/big.pdf": pdf_response()}, max_bytes=100)

    with pytest.raises(SourceError, match="너무 커요"):
        await import_from("https://example.com/big.pdf", fetcher)


async def test_network_error_becomes_user_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    fetcher = Fetcher(httpx.AsyncClient(transport=httpx.MockTransport(handler)), resolver=lambda h: ["93.184.216.34"])
    with pytest.raises(SourceError, match="연결하지 못했어요"):
        await import_from("https://example.com/paper.pdf", fetcher)


def test_import_endpoint_creates_paper_with_metadata_and_dedupes(client) -> None:
    from app.main import app
    from app.routers.papers import get_fetcher

    atom = ARXIV_ATOM.replace("1706.03762v7", "2401.99999")
    # 다른 테스트가 올린 PDF와 겹치지 않는 파일. 요청마다 같은 바이트여야 중복 검사가 된다.
    pdf = make_paper_pdf(hidden=False) + b"\n% import-test"
    app.dependency_overrides[get_fetcher] = lambda: make_fetcher(
        {
            "https://arxiv.org/pdf/2401.99999": httpx.Response(
                200, content=pdf, headers={"content-type": "application/pdf"}
            ),
            "https://export.arxiv.org/api/query?id_list=2401.99999": httpx.Response(200, text=atom),
        }
    )
    try:
        first = client.post("/api/papers/import", json={"url": "arXiv:2401.99999"})
        second = client.post("/api/papers/import", json={"url": "https://arxiv.org/abs/2401.99999"})
        bad = client.post("/api/papers/import", json={"url": "https://arxiv.org/abs/2401.00000"})
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 201, first.text
    paper = first.json()
    assert paper["title"] == "Attention Is All You Need"  # 파서 추측이 아닌 arXiv 메타데이터
    assert paper["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
    assert paper["year"] == 2017
    assert paper["arxiv_id"] == "2401.99999"
    assert paper["source_type"] == "arxiv"
    assert paper["status"] == "ready"
    assert second.status_code == 200 and second.json()["id"] == paper["id"]
    assert bad.status_code == 422
    assert "찾을 수 없어요" in bad.json()["detail"]
