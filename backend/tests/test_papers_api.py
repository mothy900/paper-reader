from tests.conftest import INJECTION, make_paper_pdf


def _upload(client, data: bytes, name: str = "paper.pdf"):
    return client.post("/api/papers", files={"file": (name, data, "application/pdf")})


def test_upload_list_blocks_and_delete(client) -> None:
    data = make_paper_pdf()
    res = _upload(client, data)
    assert res.status_code == 201
    paper = res.json()
    assert paper["status"] == "ready"
    assert paper["title"] == "Sparse Attention for Everyone"
    assert paper["language"] == "en"
    assert paper["abstract"].startswith("We study sparse attention.")
    assert paper["hidden_text_count"] == 2

    assert any(p["id"] == paper["id"] for p in client.get("/api/papers").json())

    blocks = client.get(f"/api/papers/{paper['id']}/blocks").json()
    assert blocks and len(blocks[0]["bbox"]) == 4
    # 숨은 텍스트 블록은 내려주지 않는다
    assert all(INJECTION not in b["text"] for b in blocks)
    abstract = next(b for b in blocks if b["text"].startswith("We study"))
    assert [abstract["text"][s:e] for s, e in abstract["sentences"]][0] == "We study sparse attention."
    assert next(b for b in blocks if b["text"] == "1.1 Motivation")["level"] == 2

    file_res = client.get(f"/api/papers/{paper['id']}/file")
    assert file_res.headers["content-type"] == "application/pdf"
    assert file_res.content == data

    assert client.delete(f"/api/papers/{paper['id']}").status_code == 204
    assert client.get(f"/api/papers/{paper['id']}").status_code == 404
    assert client.get(f"/api/papers/{paper['id']}/blocks").status_code == 404


def test_duplicate_upload_returns_existing_paper(client) -> None:
    data = make_paper_pdf(hidden=False)
    first = _upload(client, data, "a.pdf")
    second = _upload(client, data, "b.pdf")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    ids = [p["id"] for p in client.get("/api/papers").json()]
    assert ids.count(first.json()["id"]) == 1


def test_rejects_non_pdf(client) -> None:
    res = client.post("/api/papers", files={"file": ("x.pdf", b"hello", "application/pdf")})
    assert res.status_code == 400
