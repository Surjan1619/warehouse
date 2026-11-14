"""add is_active to users

Revision ID: b2d4a6c8e013
Revises: a1c3f5e7b902
Create Date: 2026-11-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d4a6c8e013'
down_revision: Union[str, Sequence[str], None] = 'a1c3f5e7b902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing users stay active
    op.add_column('users', sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_active')
