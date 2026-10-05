def test_upload_list_blocks_and_delete(client, sample_pdf: bytes) -> None:
    res = client.post("/api/papers", files={"file": ("paper.pdf", sample_pdf, "application/pdf")})
    assert res.status_code == 201
    paper = res.json()
    assert paper["status"] == "ready"
    assert paper["title"] == "Sparse Attention for Everyone"

    assert any(p["id"] == paper["id"] for p in client.get("/api/papers").json())

    blocks = client.get(f"/api/papers/{paper['id']}/blocks").json()
    assert blocks and len(blocks[0]["bbox"]) == 4

    file_res = client.get(f"/api/papers/{paper['id']}/file")
    assert file_res.headers["content-type"] == "application/pdf"
    assert file_res.content == sample_pdf

    assert client.delete(f"/api/papers/{paper['id']}").status_code == 204
    assert client.get(f"/api/papers/{paper['id']}").status_code == 404
    assert client.get(f"/api/papers/{paper['id']}/blocks").status_code == 404


def test_rejects_non_pdf(client) -> None:
    res = client.post("/api/papers", files={"file": ("x.pdf", b"hello", "application/pdf")})
    assert res.status_code == 400
