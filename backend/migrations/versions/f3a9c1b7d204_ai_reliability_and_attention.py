"""AI reliability + needs-attention flag

Adds (ticket "موجة التحسينات"):
- ai_runs.raw_output / finish_reason / model  (§1 raw provider output + metadata)
- conversations.needs_attention              (§2 risk-keyword flag)
- org_settings.attention_keywords            (§2 editable keyword list)

Revision ID: f3a9c1b7d204
Revises: 97e81674c563
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f3a9c1b7d204'
down_revision = '97e81674c563'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ai_runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('raw_output', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('finish_reason', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('model', sa.String(length=80), nullable=True))

    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'needs_attention', sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ))

    with op.batch_alter_table('org_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attention_keywords', sa.JSON(), nullable=True))

    # Drop the server_default now that existing rows are backfilled; the model
    # supplies the default for new rows.
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.alter_column('needs_attention', server_default=None)


def downgrade():
    with op.batch_alter_table('org_settings', schema=None) as batch_op:
        batch_op.drop_column('attention_keywords')

    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_column('needs_attention')

    with op.batch_alter_table('ai_runs', schema=None) as batch_op:
        batch_op.drop_column('model')
        batch_op.drop_column('finish_reason')
        batch_op.drop_column('raw_output')
