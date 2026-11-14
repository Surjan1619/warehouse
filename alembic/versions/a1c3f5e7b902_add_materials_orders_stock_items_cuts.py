"""add materials, orders, stock_items, cut_operations

Revision ID: a1c3f5e7b902
Revises: 79c14ac440ea
Create Date: 2026-11-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c3f5e7b902'
down_revision: Union[str, Sequence[str], None] = '79c14ac440ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=True),
        sa.Column('sku', sa.String(length=50), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('kerf_mm', sa.Integer(), server_default='3', nullable=False),
        sa.Column('min_usable_length_mm', sa.Integer(), server_default='300', nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_materials'),
        sa.UniqueConstraint('sku', name='uq_materials_sku'),
    )
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('number', sa.String(length=50), nullable=False),
        sa.Column('customer_name', sa.String(length=150), nullable=False),
        sa.Column('customer_phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('gate_type', sa.String(length=50), nullable=True),
        sa.Column('width_mm', sa.Integer(), nullable=True),
        sa.Column('height_mm', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='new', nullable=False),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_orders'),
        sa.UniqueConstraint('number', name='uq_orders_number'),
    )
    # stock_items and cut_operations refer to each other, so the foreign key
    # stock_items.cut_operation_id is added after both tables exist.
    op.create_table(
        'stock_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('length_mm', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='in_stock', nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('cut_operation_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_stock_items'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], name='fk_stock_items_material_id'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], name='fk_stock_items_location_id'),
        sa.ForeignKeyConstraint(['parent_id'], ['stock_items.id'], name='fk_stock_items_parent_id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name='fk_stock_items_order_id'),
        sa.CheckConstraint('length_mm > 0', name='ck_stock_items_length_positive'),
    )
    op.create_index('ix_stock_items_material_id', 'stock_items', ['material_id'])
    op.create_index('ix_stock_items_status', 'stock_items', ['status'])
    op.create_index('ix_stock_items_parent_id', 'stock_items', ['parent_id'])
    op.create_index('ix_stock_items_cut_operation_id', 'stock_items', ['cut_operation_id'])
    op.create_index('ix_stock_items_order_id', 'stock_items', ['order_id'])

    op.create_table(
        'cut_operations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_item_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('kerf_mm', sa.Integer(), nullable=False),
        sa.Column('kerf_loss_mm', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_cut_operations'),
        sa.ForeignKeyConstraint(['source_item_id'], ['stock_items.id'], name='fk_cut_operations_source_item_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_cut_operations_user_id'),
    )
    op.create_index('ix_cut_operations_source_item_id', 'cut_operations', ['source_item_id'])

    op.create_foreign_key(
        'fk_stock_items_cut_operation_id', 'stock_items', 'cut_operations', ['cut_operation_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_stock_items_cut_operation_id', 'stock_items', type_='foreignkey')
    op.drop_index('ix_cut_operations_source_item_id', table_name='cut_operations')
    op.drop_table('cut_operations')
    op.drop_index('ix_stock_items_order_id', table_name='stock_items')
    op.drop_index('ix_stock_items_cut_operation_id', table_name='stock_items')
    op.drop_index('ix_stock_items_parent_id', table_name='stock_items')
    op.drop_index('ix_stock_items_status', table_name='stock_items')
    op.drop_index('ix_stock_items_material_id', table_name='stock_items')
    op.drop_table('stock_items')
    op.drop_table('orders')
    op.drop_table('materials')
