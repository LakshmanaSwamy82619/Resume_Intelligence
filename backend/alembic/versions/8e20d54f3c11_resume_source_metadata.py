"""store resume source category and relative dataset path

Revision ID: 8e20d54f3c11
Revises: cc3e51a9d789
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa


revision = "8e20d54f3c11"
down_revision = "cc3e51a9d789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("source_relative_path", sa.String(length=1000), nullable=True))
    op.add_column("resumes", sa.Column("source_category", sa.String(length=100), nullable=True))
    op.create_index("ix_resumes_source_category", "resumes", ["source_category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_resumes_source_category", table_name="resumes")
    op.drop_column("resumes", "source_category")
    op.drop_column("resumes", "source_relative_path")
