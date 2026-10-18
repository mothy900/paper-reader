"""약어 추출 평가 (LLM 없음, 무료).

    DATA_DIR=<데이터 폴더> uv run python -m evals.glossary_eval

정답: evals/glossary_gold.json. 논문은 로컬 DB에서 제목 앞부분으로 찾는다.
"""

import json
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine
from app.main import run_migrations
from app.models import Paper
from app.papers import paper_glossary

GOLD = Path(__file__).with_name("glossary_gold.json")


def main() -> None:
    run_migrations()
    gold = json.loads(GOLD.read_text())["papers"]
    tp = fp = fn = 0
    with Session(engine) as session:
        papers = session.exec(select(Paper)).all()
        for g in gold:
            paper = next((p for p in papers if p.title.startswith(g["title_prefix"])), None)
            if paper is None:
                print(f"- {g['title_prefix']}: DB에 없음 (건너뜀)")
                continue
            want = {k: v.lower() for k, v in g["abbreviations"].items()}
            got = {t.short: (t.long or "").lower() for t in paper_glossary(session, paper.id) if t.kind == "abbr"}
            ok = {k for k in want if got.get(k) == want[k]}
            tp += len(ok)
            fn += len(want) - len(ok)
            fp += len(set(got) - ok)
            print(f"- {g['title_prefix']}: {len(ok)}/{len(want)}")
            for k in sorted(set(want) - ok):
                print(f"    놓침 {k} = {want[k]} (추출: {got.get(k)})")
            for k in sorted(set(got) - set(want)):
                print(f"    오탐 {k} = {got[k]}")
    if tp + fp and tp + fn:
        print(f"정밀도 {tp / (tp + fp):.0%}, 재현율 {tp / (tp + fn):.0%}")


if __name__ == "__main__":
    main()
