"""add table block type

Revision ID: 6cc01183a7bf
Revises: bedbf88242f3
Create Date: 2026-10-09 16:49:42.326467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '6cc01183a7bf'
down_revision: Union[str, Sequence[str], None] = 'bedbf88242f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite는 enum을 문자열로 저장해 바꿀 게 없다. Postgres는 네이티브 enum 타입에 값을 추가한다.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE blocktype ADD VALUE IF NOT EXISTS 'table'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres는 enum 값을 지울 수 없다. table 블록은 재파싱 전까지 남는다.
    pass
