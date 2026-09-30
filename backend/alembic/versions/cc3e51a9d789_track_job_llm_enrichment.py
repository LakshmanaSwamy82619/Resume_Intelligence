"""track whether job requirement enrichment used the LLM

Revision ID: cc3e51a9d789
Revises: 6d4216468ac9
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa


revision = "cc3e51a9d789"
down_revision = "6d4216468ac9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_descriptions",
        sa.Column("llm_enrichment_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("job_descriptions", "llm_enrichment_used")
