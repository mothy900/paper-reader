import json

import pytest

from app.llm.client import get_llm_client
from tests.conftest import make_paper_pdf
from tests.fake_llm import FakeClient

SENTENCE_REPLY = [
    "<translation>우리는 희소 어텐션을 연구한다.</translation>",
    "<explanation>쉬운 설명</explanation><role>문제 제기</role><terms>- 어텐션(attention): 집중</terms>",
]


def _events(res) -> list[tuple[str, dict]]:
    out = []
    for chunk in res.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.split("\n"))
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture(autouse=True)
def clean_llm_tables(client):
    """결과 캐시는 논문이 아니라 텍스트 기준이라, 테스트끼리 섞이지 않게 비운다."""
    from sqlmodel import Session, delete

    from app.db import engine
    from app.models import ExplainHistory, LlmCall, LlmResult, UserProfile

    with Session(engine) as session:
        for table in (LlmResult, LlmCall, ExplainHistory, UserProfile):
            session.exec(delete(table))
        session.commit()


@pytest.fixture
def paper(client) -> dict:
    data = make_paper_pdf(hidden=False) + b"\n% llm-test"
    return client.post("/api/papers", files={"file": ("p.pdf", data, "application/pdf")}).json()


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


def _abstract_focus(client, paper: dict, source: str = "selection", text: str | None = None) -> dict:
    blocks = client.get(f"/api/papers/{paper['id']}/blocks").json()
    b = next(b for b in blocks if b["text"].startswith("We study"))
    selected = text or b["text"]
    start = b["text"].find(selected)
    return {
        "source": source,
        "text": selected,
        "block_ids": [b["id"]],
        "ranges": [{"block_id": b["id"], "start": start, "end": start + len(selected)}],
        "sentence_ids": [f"{b['id']}:0"],
    }


def test_explain_sentence_streams_sections_and_records_cost(client, paper, fake) -> None:
    llm = fake(FakeClient(SENTENCE_REPLY, usage=(1000, 200)))
    res = client.post(f"/api/papers/{paper['id']}/explain", json={"focus": _abstract_focus(client, paper)})

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = _events(res)
    assert events[0] == ("meta", {"task": "explain_sentence", "model": "claude-haiku-4-5", "cached": False})
    text = {}
    for name, data in events:
        if name == "section":
            text[data["name"]] = text.get(data["name"], "") + data["delta"]
    assert text["translation"] == "우리는 희소 어텐션을 연구한다."
    assert set(text) == {"translation", "explanation", "role", "terms"}
    done = events[-1]
    assert done[0] == "done" and done[1]["cost_usd"] == pytest.approx(0.002)

    # 컨텍스트: 초록·섹션 제목·문단이 들어가고, 논문 텍스트는 <paper> 안에
    params = llm.calls[0]
    prompt = params["messages"][0]["content"][-1]["text"]
    assert "<paper>" in prompt and "We study sparse attention." in prompt
    assert "<reader>" in params["system"]

    usage = client.get(f"/api/papers/{paper['id']}/usage").json()
    assert usage == {"cost_usd": pytest.approx(0.002), "calls": 1}


def test_second_identical_request_is_served_from_cache(client, paper, fake) -> None:
    llm = fake(FakeClient(SENTENCE_REPLY))
    focus = _abstract_focus(client, paper)
    client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus})
    events = _events(client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus}))

    assert len(llm.calls) == 1
    assert events[0][1]["cached"] is True
    assert events[-1] == ("done", {"model": "claude-haiku-4-5", "cached": True, "cost_usd": 0.0})
    # 같은 해설을 다시 연 것이라 기록은 하나
    assert len(client.get(f"/api/papers/{paper['id']}/history").json()) == 1


def test_short_selection_uses_word_task(client, paper, fake) -> None:
    llm = fake(FakeClient(["<in_paper>a</in_paper><general>b</general><plain>c</plain>"]))
    focus = _abstract_focus(client, paper, text="sparse attention")
    events = _events(client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus}))

    assert events[0][1]["task"] == "explain_word"
    assert "<selection>sparse attention</selection>" in llm.calls[0]["messages"][0]["content"][-1]["text"]


def test_deep_detail_uses_sonnet_with_fallback(client, paper, fake) -> None:
    llm = fake(FakeClient(SENTENCE_REPLY))
    events = _events(
        client.post(
            f"/api/papers/{paper['id']}/explain", json={"focus": _abstract_focus(client, paper), "detail": "deep"}
        )
    )

    params = llm.calls[0]
    assert params["model"] == "claude-sonnet-5-5"
    assert params["fallbacks"] == "default"
    assert params["output_config"] == {"effort": "low"}
    assert events[0][1]["model"] == "claude-sonnet-5-5"


def test_refusal_is_reported_and_not_cached(client, paper, fake) -> None:
    llm = fake(FakeClient(["<translation>부분"], stop_reason="refusal"))
    focus = _abstract_focus(client, paper)
    events = _events(client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus}))

    assert events[-1][0] == "refused"
    assert events[-1][1]["category"] == "bio"
    # 다시 요청하면 캐시가 아니라 다시 호출한다
    client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus})
    assert len(llm.calls) == 2


def test_profile_round_trip_and_changes_cache_key(client, paper, fake) -> None:
    llm = fake(FakeClient(SENTENCE_REPLY))
    focus = _abstract_focus(client, paper)
    assert client.get("/api/profile").json() is None

    client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus})
    saved = client.put("/api/profile", json={"background": "개발자, ML 입문", "level": "intermediate"}).json()
    assert saved == {"background": "개발자, ML 입문", "level": "intermediate"}
    client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus})

    # 프로필이 바뀌면 설명도 달라져야 하므로 캐시를 쓰지 않는다
    assert len(llm.calls) == 2
    assert "개발자, ML 입문" in llm.calls[1]["system"]


def test_translate_paragraph(client, paper, fake) -> None:
    llm = fake(FakeClient(["<translation>번역문</translation>"]))
    blocks = client.get(f"/api/papers/{paper['id']}/blocks").json()
    block = next(b for b in blocks if b["text"].startswith("Transformers"))
    events = _events(client.post(f"/api/papers/{paper['id']}/translate", json={"block_id": block["id"]}))

    assert ("section", {"name": "translation", "delta": "번역문"}) in events
    assert "Transformers rely on self-attention" in llm.calls[0]["messages"][0]["content"][-1]["text"]


def test_unknown_block_is_rejected(client, paper, fake) -> None:
    fake(FakeClient([]))
    focus = {"source": "block", "text": "x", "block_ids": ["p9-99"], "ranges": [], "sentence_ids": []}
    assert client.post(f"/api/papers/{paper['id']}/explain", json={"focus": focus}).status_code == 422
