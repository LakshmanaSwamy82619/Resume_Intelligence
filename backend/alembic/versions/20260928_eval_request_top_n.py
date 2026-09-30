"""store the requested evaluation cutoff on the HR handoff

Revision ID: 20260928_eval_request_top_n
Revises: 20260928_eval_requests
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260928_eval_request_top_n"
down_revision = "20260928_eval_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_requests",
        sa.Column("top_n", sa.Integer(), server_default="5", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("evaluation_requests", "top_n")
