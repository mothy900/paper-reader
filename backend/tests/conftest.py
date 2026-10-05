import os
import tempfile
from collections.abc import Iterator

import pymupdf
import pytest

# app 모듈이 import 되기 전에 임시 데이터 디렉터리를 지정한다
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="reader-test-")

LOREM = (
    "Transformers rely on self-attention to model long range dependencies. "
    "We propose a sparse variant that reduces the quadratic cost while "
    "preserving accuracy on standard language modeling benchmarks."
)


def make_two_column_pdf() -> bytes:
    """제목 + 2단 본문 + 섹션 제목 + 캡션이 있는 논문 형태의 PDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_textbox((72, 60, 540, 100), "Sparse Attention for Everyone", fontsize=18, fontname="hebo", align=1)
    # 왼쪽 단
    page.insert_textbox((72, 115, 296, 140), "1 Introduction", fontsize=12, fontname="hebo")
    page.insert_textbox((72, 145, 296, 300), LOREM, fontsize=10, fontname="helv")
    page.insert_textbox((72, 310, 296, 330), "Figure 1: Overview of the method.", fontsize=9, fontname="helv")
    page.insert_textbox((100, 250, 200, 262), "56-layer", fontsize=7, fontname="helv")
    # 오른쪽 단
    page.insert_textbox((316, 115, 540, 140), "2 Method", fontsize=12, fontname="hebo")
    page.insert_textbox((316, 145, 540, 300), LOREM, fontsize=10, fontname="helv")
    page.insert_textbox((300, 750, 312, 770), "1", fontsize=9, fontname="helv")
    # arXiv 옆면 스탬프처럼 회전된 큰 글씨
    page.insert_text((30, 600), "arXiv:2401.00001v1 [cs.CL]", fontsize=20, fontname="helv", rotate=90)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def sample_pdf() -> bytes:
    return make_two_column_pdf()


@pytest.fixture
def client() -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
