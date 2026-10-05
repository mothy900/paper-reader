"""파서가 바뀐 뒤 기존 논문을 다시 파싱한다.

    uv run python -m app.scripts.reparse          # parser_version이 다른 논문만
    uv run python -m app.scripts.reparse --all    # 전부
"""

import hashlib
import sys

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.main import run_migrations
from app.models import Paper
from app.papers import apply_parse
from app.parsing.pymupdf_parser import PARSER_VERSION
from app.storage import get_storage


def main(reparse_all: bool) -> None:
    run_migrations()
    storage = get_storage()
    with Session(engine) as session:
        papers = session.exec(select(Paper).where(Paper.user_id == settings.default_user_id)).all()
        for paper in papers:
            if not reparse_all and paper.parser_version == PARSER_VERSION:
                continue
            data = storage.load(paper.file_key)
            paper.sha256 = hashlib.sha256(data).hexdigest()
            apply_parse(session, paper, data)
            session.add(paper)
            session.commit()
            print(f"{paper.status:7} {paper.id} {paper.title[:60]}")


if __name__ == "__main__":
    main(reparse_all="--all" in sys.argv)
