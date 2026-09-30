"""store human skill-gap ground truth with evaluation labels

Revision ID: f24c8ad1920e
Revises: cc3e51a9d789, 20260928_eval_request_top_n
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "f24c8ad1920e"
down_revision = ("cc3e51a9d789", "20260928_eval_request_top_n")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluation_labels", sa.Column("skill_statuses", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    op.drop_column("evaluation_labels", "skill_statuses")
