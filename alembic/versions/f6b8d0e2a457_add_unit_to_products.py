"""add unit to products

Revision ID: f6b8d0e2a457
Revises: 0ba50d8723d9
Create Date: 2026-11-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b8d0e2a457'
down_revision: Union[str, Sequence[str], None] = '0ba50d8723d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Products that already exist are counted in pieces
    op.add_column('products', sa.Column('unit', sa.String(length=10), server_default='шт', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('products', 'unit')
