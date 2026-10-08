"""add_overdue_to_status_enum

Revision ID: e99be3bd4bac
Revises: 33596729baaa
Create Date: 2026-10-07 20:07:03.742080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e99be3bd4bac'
down_revision: Union[str, Sequence[str], None] = '33596729baaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Używamy execute, aby dodać nową wartość do typu ENUM w PostgreSQL
    op.execute("ALTER TYPE status_enum ADD VALUE IF NOT EXISTS 'OVERDUE'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
