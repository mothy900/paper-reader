from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

import app.models  # noqa: F401 - 메타데이터에 테이블 등록
from app.config import settings
from app.db import engine

config = context.config

if config.config_file_name is not None:
    # 앱 시작 시 마이그레이션을 돌려도 uvicorn 로거가 꺼지지 않게 한다
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata
# SQLite는 ALTER가 제한적이라 batch 모드로 테이블을 재생성한다. Postgres에서는 영향 없음.
render_as_batch = engine.dialect.name == "sqlite"


def run_migrations_offline() -> None:
    context.configure(
        url=settings.resolved_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=render_as_batch,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=render_as_batch,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
