"""Order editing: pricing + revision history

Adds (ticket §3):
- orders.delivery_fee / price_pending / places_count
- orders.revision / revisions  (in-place edits keep the same order id)

Revision ID: b7c2e9f41a30
Revises: f3a9c1b7d204
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7c2e9f41a30'
down_revision = 'f3a9c1b7d204'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('delivery_fee', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column(
            'price_pending', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('places_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column(
            'revision', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('revisions', sa.JSON(), nullable=True))

    # Drop server defaults now that existing rows are backfilled.
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('price_pending', server_default=None)
        batch_op.alter_column('revision', server_default=None)


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('revisions')
        batch_op.drop_column('revision')
        batch_op.drop_column('places_count')
        batch_op.drop_column('price_pending')
        batch_op.drop_column('delivery_fee')
