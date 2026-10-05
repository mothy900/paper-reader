from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.resolved_database_url,
    connect_args={"check_same_thread": False}
    if settings.resolved_database_url.startswith("sqlite")
    else {},
)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
