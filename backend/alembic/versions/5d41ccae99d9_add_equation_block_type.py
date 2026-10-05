"""add equation block type

Revision ID: 5d41ccae99d9
Revises: 61a85f940069
Create Date: 2026-10-05 21:05:57.676592

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5d41ccae99d9'
down_revision: Union[str, Sequence[str], None] = '61a85f940069'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite는 enum을 문자열로 저장해 바꿀 게 없다. Postgres는 네이티브 enum 타입에 값을 추가한다.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE blocktype ADD VALUE IF NOT EXISTS 'equation'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres는 enum 값을 지울 수 없다. equation 블록은 재파싱 전까지 남는다.
    pass
