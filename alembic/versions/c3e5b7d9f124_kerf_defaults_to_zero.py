"""kerf defaults to zero

Revision ID: c3e5b7d9f124
Revises: b2d4a6c8e013
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e5b7d9f124'
down_revision: Union[str, Sequence[str], None] = 'b2d4a6c8e013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cuts no longer consume length: reset existing materials and the default."""
    op.execute("UPDATE materials SET kerf_mm = 0")
    op.alter_column('materials', 'kerf_mm', existing_type=sa.Integer(), server_default='0')


def downgrade() -> None:
    """Restore the old default. The previous per-material values are not recoverable."""
    op.alter_column('materials', 'kerf_mm', existing_type=sa.Integer(), server_default='3')
