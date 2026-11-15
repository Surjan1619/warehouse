"""add activity_log

Revision ID: e5a7d9f1b346
Revises: d4f6c8e0a235
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5a7d9f1b346'
down_revision: Union[str, Sequence[str], None] = 'd4f6c8e0a235'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'activity_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=30), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=True),
        sa.Column('stock_item_id', sa.Integer(), nullable=True),
        sa.Column('cut_operation_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('length_mm', sa.Integer(), server_default='0', nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_activity_log'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_activity_log_user_id'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], name='fk_activity_log_material_id'),
        sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], name='fk_activity_log_stock_item_id'),
        sa.ForeignKeyConstraint(
            ['cut_operation_id'], ['cut_operations.id'], name='fk_activity_log_cut_operation_id'
        ),
    )
    op.create_index('ix_activity_log_created_at', 'activity_log', ['created_at'])
    op.create_index('ix_activity_log_user_id', 'activity_log', ['user_id'])
    op.create_index('ix_activity_log_action', 'activity_log', ['action'])
    op.create_index('ix_activity_log_material_id', 'activity_log', ['material_id'])
    op.create_index('ix_activity_log_stock_item_id', 'activity_log', ['stock_item_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_activity_log_stock_item_id', table_name='activity_log')
    op.drop_index('ix_activity_log_material_id', table_name='activity_log')
    op.drop_index('ix_activity_log_action', table_name='activity_log')
    op.drop_index('ix_activity_log_user_id', table_name='activity_log')
    op.drop_index('ix_activity_log_created_at', table_name='activity_log')
    op.drop_table('activity_log')
