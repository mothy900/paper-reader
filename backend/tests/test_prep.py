import json

import pymupdf
import pytest

from app.llm.client import get_llm_client
from tests.fake_llm import FakeClient
from tests.test_llm_api import _events

METHODS_1 = "Radish cubes were brined in 5% and 10% NaCl solutions for 300 min. Each treatment was performed in triplicate."
METHODS_2 = (
    "The dataset was split into training (70%), validation (15%), and test (15%) sets. "
    "Model performance was evaluated using RMSE and R2."
)
RESULTS = "The ensemble model achieved the highest accuracy among all models tested in this study."
SUPPLEMENT = "Additional measurements are provided in Supplementary Table S1 for all samples."


def make_methods_pdf(methods: bool = True) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=794)
    page.insert_textbox((40, 40, 555, 80), "Brining Radish With Machine Learning", fontsize=16, fontname="hebo", align=1)
    page.insert_text((40, 110), "1. Introduction", fontsize=10, fontname="hebo")
    page.insert_textbox((40, 118, 555, 160), "Brining is a key step in kimchi production and takes a long time.", fontsize=9, fontname="helv")
    heading = "2. Materials and methods" if methods else "2. Our approach"
    page.insert_text((40, 180), heading, fontsize=10, fontname="hebo")
    page.insert_textbox((40, 188, 555, 230), METHODS_1, fontsize=9, fontname="helv")
    page.insert_textbox((40, 235, 555, 280), METHODS_2, fontsize=9, fontname="helv")
    page.insert_text((40, 300), "Table 1. Treatment conditions", fontsize=8, fontname="helv")
    for r in range(3):
        page.insert_text((60, 314 + r * 12), f"T{r + 1}", fontsize=7, fontname="helv")
        page.insert_text((160, 314 + r * 12), f"{5 * (r + 1)} %", fontsize=7, fontname="helv")
    page.insert_text((40, 380), "3. Results", fontsize=10, fontname="hebo")
    page.insert_textbox((40, 388, 555, 430), RESULTS, fontsize=9, fontname="helv")
    page.insert_textbox((40, 435, 555, 480), SUPPLEMENT, fontsize=9, fontname="helv")
    page.insert_text((40, 500), "4. Conclusions", fontsize=10, fontname="hebo")
    page.insert_textbox((40, 508, 555, 550), "Machine learning predicted mass transfer well in this setting.", fontsize=9, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def methods_paper(client) -> dict:
    data = make_methods_pdf() + b"\n% prep-test"
    return client.post("/api/papers", files={"file": ("m.pdf", data, "application/pdf")}).json()


@pytest.fixture
def blocks(client, methods_paper) -> list[dict]:
    return client.get(f"/api/papers/{methods_paper['id']}/blocks").json()


def _sid(blocks: list[dict], text_start: str, idx: int = 0) -> str:
    b = next(b for b in blocks if b["text"].startswith(text_start))
    return f"{b['id']}:{idx}"


def _data_result(blocks: list[dict]) -> dict:
    table = next(b for b in blocks if b["type"] == "table")
    s_brine = _sid(blocks, "Radish cubes", 0)
    s_split = _sid(blocks, "The dataset was split", 0)
    field = lambda value, status, ev, calc="": {"value": value, "status": status, "calculation": calc, "evidence": ev}  # noqa: E731
    return {
        "applicable": True,
        "not_applicable_reason": "",
        "fields": {
            "inputs": field("NaCl 5%, 10%", "stated", [{"ref": s_brine, "quote": "brined in 5% and 10% NaCl solutions"}]),
            "outputs": field("질량 변화", "stated", [{"ref": s_brine, "quote": "this quote is not in the paper"}]),
            # 근거에 없는 숫자(96)를 "명시"라고 했다 → 추정으로 내려야 한다
            "sample_size": field("96개", "stated", [{"ref": s_brine, "quote": "performed in triplicate"}]),
            "validation": field("70/15/15 분할", "stated", [{"ref": s_split, "quote": "split into training (70%)"}]),
            "metrics": field("논문에 명시 안 됨", "not_stated", [{"ref": f"table:{table['id']}", "quote": "RMSE 0.12"}]),
        },
        "warnings": [{"text": "테스트셋이 작을 수 있다", "evidence": [{"ref": s_split, "quote": "test (15%) sets"}]}],
        "questions": ["총 샘플 수는 몇 개인가요?"],
    }


@pytest.fixture
def fake(client):
    from app.main import app

    holder: dict[str, FakeClient] = {}

    def use(fake_client: FakeClient) -> FakeClient:
        holder["c"] = fake_client
        app.dependency_overrides[get_llm_client] = lambda: holder["c"]
        return fake_client

    yield use
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_llm_tables(client):
    from sqlmodel import Session, delete

    from app.db import engine
    from app.models import ExplainHistory, LlmCall, LlmResult, UserProfile

    with Session(engine) as session:
        for table in (LlmResult, LlmCall, ExplainHistory, UserProfile):
            session.exec(delete(table))
        session.commit()


def test_data_card_verifies_evidence_and_numbers(client, methods_paper, blocks, fake) -> None:
    raw = json.dumps(_data_result(blocks))
    llm = fake(FakeClient([raw[:50], raw[50:]], usage=(8000, 1500)))
    events = _events(client.post(f"/api/papers/{methods_paper['id']}/prep/data"))

    meta = events[0][1]
    assert meta["task"] == "prep_data" and meta["model"] == "claude-sonnet-5-5"
    assert meta["scope"] == "섹션: 2. Materials and methods"
    assert len(meta["tables"]) == 1

    done = events[-1]
    assert done[0] == "done"
    result = done[1]["result"]
    fields = result["fields"]
    assert fields["inputs"]["evidence"][0]["check"] == "verified"
    assert fields["outputs"]["evidence"][0]["check"] == "unverified"
    assert fields["sample_size"]["status"] == "inferred"  # 96은 근거에 없다
    assert fields["sample_size"]["numbers_unverified"] == ["96"]
    assert fields["validation"]["status"] == "stated"
    assert fields["metrics"]["evidence"][0]["check"] == "image"  # 표 근거는 자동 확인 불가
    assert fields["inputs"]["evidence"][0]["block_id"]
    assert result["supplementary"] and "Supplementary Table S1" in result["supplementary"][0]["snippet"]

    params = llm.calls[0]
    assert params["output_config"]["effort"] == "medium"
    assert params["output_config"]["format"]["type"] == "json_schema"
    content = params["messages"][0]["content"]
    assert any(c.get("type") == "image" for c in content)  # 표 이미지 첨부
    prompt = content[-1]["text"]
    assert METHODS_1.split(".")[0] in prompt and RESULTS not in prompt  # Methods만 보낸다
    assert 'id="' in prompt


def test_prep_is_cached_and_readable_without_calling(client, methods_paper, blocks, fake) -> None:
    llm = fake(FakeClient([json.dumps(_data_result(blocks))]))
    assert client.get(f"/api/papers/{methods_paper['id']}/prep").json()["data"] is None

    client.post(f"/api/papers/{methods_paper['id']}/prep/data")
    again = _events(client.post(f"/api/papers/{methods_paper['id']}/prep/data"))
    stored = client.get(f"/api/papers/{methods_paper['id']}/prep").json()

    assert len(llm.calls) == 1
    assert again[-1][1]["cached"] is True
    assert stored["data"]["fields"]["sample_size"]["status"] == "inferred"
    assert stored["data_scope"] == "섹션: 2. Materials and methods"
    assert stored["concepts"] is None


def test_concepts_card_drops_unknown_section_refs(client, methods_paper, blocks, fake) -> None:
    intro = next(b for b in blocks if b["text"] == "1. Introduction")
    result = {
        "concepts": [
            {"name": "염지", "original": "brining", "what": "소금물에 담그기", "why": "핵심 공정", "section_ref": intro["id"]},
            {"name": "앙상블", "original": "ensemble", "what": "여러 모델", "why": "비교 대상", "section_ref": "p99-1"},
        ]
    }
    llm = fake(FakeClient([json.dumps(result)]))
    events = _events(client.post(f"/api/papers/{methods_paper['id']}/prep/concepts"))

    concepts = events[-1][1]["result"]["concepts"]
    assert [c["section_ref"] for c in concepts] == [intro["id"], ""]
    prompt = llm.calls[0]["messages"][0]["content"][-1]["text"]
    assert "Brining is a key step" in prompt  # 서론
    assert "Machine learning predicted" in prompt  # 결론
    assert llm.calls[0]["output_config"]["effort"] == "low"


def test_falls_back_to_whole_body_without_methods_section(client, fake) -> None:
    data = make_methods_pdf(methods=False) + b"\n% prep-fallback"
    paper = client.post("/api/papers", files={"file": ("n.pdf", data, "application/pdf")}).json()
    fake(FakeClient(["{}"]))
    events = _events(client.post(f"/api/papers/{paper['id']}/prep/data"))
    assert events[0][1]["scope"] == "Methods 섹션을 찾지 못해 본문 전체"


def test_invalid_json_is_reported_not_cached(client, methods_paper, fake) -> None:
    llm = fake(FakeClient(['{"applicable": tru']))
    events = _events(client.post(f"/api/papers/{methods_paper['id']}/prep/data"))
    assert events[-1][0] == "error"
    client.post(f"/api/papers/{methods_paper['id']}/prep/data")
    assert len(llm.calls) == 2


def test_table_click_uses_table_task(client, methods_paper, blocks, fake) -> None:
    table = next(b for b in blocks if b["type"] == "table")
    llm = fake(FakeClient(["<summary>요약</summary><how_to_read>읽기</how_to_read><key_points>- 값</key_points>"]))
    focus = {
        "source": "block",
        "text": table["text"],
        "block_ids": [table["id"]],
        "ranges": [{"block_id": table["id"], "start": 0, "end": len(table["text"])}],
        "sentence_ids": [f"{table['id']}:0"],
    }
    events = _events(client.post(f"/api/papers/{methods_paper['id']}/explain", json={"focus": focus}))
    assert events[0][1]["task"] == "explain_table"
    assert llm.calls[0]["messages"][0]["content"][0]["type"] == "image"


def test_numbers_from_table_images_are_not_downgraded(client, methods_paper, blocks, fake) -> None:
    table = next(b for b in blocks if b["type"] == "table")
    result = _data_result(blocks)
    result["fields"]["metrics"] = {
        "value": "R^{2} 0.987",
        "status": "stated",
        "calculation": "",
        "evidence": [{"ref": f"table:{table['id']}", "quote": "R2 0.987"}],
    }
    fake(FakeClient([json.dumps(result)]))
    events = _events(client.post(f"/api/papers/{methods_paper['id']}/prep/data"))
    metrics = events[-1][1]["result"]["fields"]["metrics"]
    assert metrics["status"] == "stated"
    assert metrics["numbers_unverified"]  # 확인 못 한 숫자는 표시만 한다


def test_numbers_elsewhere_in_paper_do_not_downgrade(client, methods_paper, blocks, fake) -> None:
    # 300 min은 근거 문장(분할)에는 없지만 논문의 다른 문장에 있다 → 지어낸 숫자가 아니다
    result = _data_result(blocks)
    result["fields"]["validation"]["value"] = "70/15/15 분할, 300 min 측정 자료"
    fake(FakeClient([json.dumps(result)]))
    events = _events(client.post(f"/api/papers/{methods_paper['id']}/prep/data"))
    validation = events[-1][1]["result"]["fields"]["validation"]
    assert validation["status"] == "stated"
    assert validation["numbers_unverified"] == []


def test_number_boundaries() -> None:
    from app.llm.prep import _has_number

    assert _has_number("trained ResNet-110 for 64k iterations", "110")
    assert not _has_number("we used 1100 images", "110")
    assert not _has_number("an error of 2.110 percent", "110")
