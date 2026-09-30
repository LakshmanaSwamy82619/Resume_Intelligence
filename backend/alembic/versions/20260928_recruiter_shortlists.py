"""add persistent recruiter shortlists

Revision ID: 20260928_shortlists
Revises: f24c8ad1920e
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260928_shortlists"
down_revision = "f24c8ad1920e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recruiter_shortlists",
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("search_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recruiter_shortlists_owner_user_id", "recruiter_shortlists", ["owner_user_id"])
    op.create_table(
        "recruiter_shortlist_candidates",
        sa.Column("shortlist_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("source_search_id", sa.String(length=36), nullable=True),
        sa.Column("stage", sa.String(length=30), server_default="saved", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shortlist_id"], ["recruiter_shortlists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_search_id"], ["searches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shortlist_id", "candidate_id", name="uq_shortlist_candidate"),
    )
    op.create_index("ix_recruiter_shortlist_candidates_shortlist_id", "recruiter_shortlist_candidates", ["shortlist_id"])
    op.create_index("ix_recruiter_shortlist_candidates_candidate_id", "recruiter_shortlist_candidates", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_recruiter_shortlist_candidates_candidate_id", table_name="recruiter_shortlist_candidates")
    op.drop_index("ix_recruiter_shortlist_candidates_shortlist_id", table_name="recruiter_shortlist_candidates")
    op.drop_table("recruiter_shortlist_candidates")
    op.drop_index("ix_recruiter_shortlists_owner_user_id", table_name="recruiter_shortlists")
    op.drop_table("recruiter_shortlists")
