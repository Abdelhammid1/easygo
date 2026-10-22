"""Debounce settings on ai_settings

Adds (ticket §4): ai_settings.debounce_seconds / debounce_max_seconds — coalesce
rapid customer messages into a single AI reply.

Revision ID: c4d8e1067b92
Revises: b7c2e9f41a30
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c4d8e1067b92'
down_revision = 'b7c2e9f41a30'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ai_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'debounce_seconds', sa.Integer(), nullable=False, server_default='5'))
        batch_op.add_column(sa.Column(
            'debounce_max_seconds', sa.Integer(), nullable=False, server_default='15'))

    with op.batch_alter_table('ai_settings', schema=None) as batch_op:
        batch_op.alter_column('debounce_seconds', server_default=None)
        batch_op.alter_column('debounce_max_seconds', server_default=None)


def downgrade():
    with op.batch_alter_table('ai_settings', schema=None) as batch_op:
        batch_op.drop_column('debounce_max_seconds')
        batch_op.drop_column('debounce_seconds')
