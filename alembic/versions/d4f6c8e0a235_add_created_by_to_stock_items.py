"""add created_by to stock_items

Revision ID: d4f6c8e0a235
Revises: c3e5b7d9f124
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6c8e0a235'
down_revision: Union[str, Sequence[str], None] = 'c3e5b7d9f124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('stock_items', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.create_index('ix_stock_items_created_by_id', 'stock_items', ['created_by_id'])
    op.create_foreign_key('fk_stock_items_created_by_id', 'stock_items', 'users', ['created_by_id'], ['id'])
    # Pieces produced by a cut were created by whoever made that cut.
    # Pieces received before this revision keep an unknown author.
    op.execute(
        """
        UPDATE stock_items AS s
        SET created_by_id = c.user_id
        FROM cut_operations AS c
        WHERE s.cut_operation_id = c.id AND c.user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_stock_items_created_by_id', 'stock_items', type_='foreignkey')
    op.drop_index('ix_stock_items_created_by_id', table_name='stock_items')
    op.drop_column('stock_items', 'created_by_id')
