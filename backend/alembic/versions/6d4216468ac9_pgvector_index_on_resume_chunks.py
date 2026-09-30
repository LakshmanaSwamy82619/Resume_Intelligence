"""pgvector extension + ANN index on resume_chunks.embedding

This migration is a no-op on SQLite (the local/dev/test default): the
pgvector extension and ivfflat index only make sense, and only apply,
against Postgres. On Postgres, this is what turns semantic retrieval from
the brute-force numpy scan (app/retrieval/vector.py's SQLite fallback path)
into a real approximate-nearest-neighbor index capable of the 10,000+
resume scale target (Section 26/41).

Revision ID: 6d4216468ac9
Revises: 2899feec1254
Create Date: 2026-09-26 10:13:48.305835

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6d4216468ac9'
down_revision = '2899feec1254'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # ivfflat requires an estimate of row count for `lists`; 100 is a
    # reasonable default for a few thousand-to-tens-of-thousands of rows
    # and should be re-tuned (see pgvector docs) once real data volume is
    # known. cosine distance (vector_cosine_ops) matches the L2-normalized
    # embeddings produced by every EmbeddingProvider in this project.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_resume_chunks_embedding_ivfflat "
        "ON resume_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_resume_chunks_embedding_ivfflat")
