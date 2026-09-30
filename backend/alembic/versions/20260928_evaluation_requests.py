"""add HR evaluation handoff requests

Revision ID: 20260928_eval_requests
Revises: 71d3492bcf18
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260928_eval_requests"
down_revision = "71d3492bcf18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_requests",
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("completed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("evaluation_result_id", sa.String(length=36), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["evaluation_result_id"], ["evaluation_results.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_requests_dataset_id", "evaluation_requests", ["dataset_id"])
    op.create_index("ix_evaluation_requests_status", "evaluation_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_requests_status", table_name="evaluation_requests")
    op.drop_index("ix_evaluation_requests_dataset_id", table_name="evaluation_requests")
    op.drop_table("evaluation_requests")
