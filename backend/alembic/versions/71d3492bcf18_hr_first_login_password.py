"""require HR users to change their temporary password on first login

Revision ID: 71d3492bcf18
Revises: 8e20d54f3c11
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa


revision = "71d3492bcf18"
down_revision = "8e20d54f3c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
