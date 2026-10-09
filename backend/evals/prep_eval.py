"""데이터 뼈대 카드 평가. 실제 API를 부르므로 비용이 든다 (저장된 결과가 있으면 무료).

    DATA_DIR=<데이터 폴더> uv run python -m evals.prep_eval

정답: evals/prep_gold.json. 논문은 로컬 DB에서 제목 앞부분으로 찾는다.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.llm.client import get_llm_client
from app.main import run_migrations
from app.models import Paper
from app.routers.llm import _prep_request, _verifier
from app.llm.runner import run_task
from app.storage import get_storage

GOLD = Path(__file__).with_name("prep_gold.json")


async def run_one(paper: Paper) -> tuple[dict | None, float, bool]:
    with Session(engine) as session:
        req, _ = _prep_request(session, get_storage(), paper, "data")
    result, cost, cached = None, 0.0, False
    async for e in run_task(req, get_llm_client(), _verifier("data", paper.id)):
        if e["event"] == "done":
            result, cost, cached = e["data"]["result"], e["data"]["cost_usd"], e["data"]["cached"]
        elif e["event"] in ("error", "refused"):
            print(f"  ! {e['event']}: {e['data']['message']}")
    return result, cost, cached


def score(result: dict, gold_fields: dict) -> list[tuple[str, bool, bool, str]]:
    rows = []
    for name, g in gold_fields.items():
        f = result["fields"].get(name, {})
        status_ok = f.get("status") in g["status"]
        missing = [pat for pat in g["must"] if not re.search(pat, f.get("value", ""), re.IGNORECASE)]
        rows.append((name, status_ok, not missing, f"{f.get('status')}: {f.get('value', '')[:90]}" + (f"  (빠짐: {missing})" if missing else "")))
    return rows


async def main() -> int:
    run_migrations()
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    total_cost = 0.0
    status_hits = keyword_hits = n = 0
    evidence_verified = evidence_total = 0
    with Session(engine) as session:
        papers = session.exec(select(Paper).where(Paper.user_id == settings.default_user_id)).all()
    for item in gold["papers"]:
        paper = next((p for p in papers if p.title.startswith(item["title_prefix"])), None)
        if paper is None:
            print(f"- 건너뜀 (DB에 없음): {item['title_prefix']}")
            continue
        print(f"\n# {paper.title[:70]}")
        result, cost, cached = await run_one(paper)
        total_cost += cost
        if result is None:
            continue
        for name, s_ok, k_ok, detail in score(result, item["fields"]):
            n += 1
            status_hits += s_ok
            keyword_hits += k_ok
            print(f"  {'✓' if s_ok else '✗'}상태 {'✓' if k_ok else '✗'}내용  {name:12} {detail}")
        for f in result["fields"].values():
            for ev in f.get("evidence", []):
                evidence_total += 1
                evidence_verified += ev["check"] in ("verified", "image")
        print(f"  비용 {cost * 100:.2f}¢{' (저장된 결과)' if cached else ''}")
    if n:
        print(f"\n상태 정확도 {status_hits}/{n}, 내용 정확도 {keyword_hits}/{n}, "
              f"근거 확인 {evidence_verified}/{evidence_total}, 총비용 {total_cost * 100:.1f}¢")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
