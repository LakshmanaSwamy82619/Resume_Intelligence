"""
Semantic vector retrieval (Section 9/10).

Two code paths, selected by the active DB dialect:
  - Postgres + pgvector: real ANN search via the `<=>` cosine-distance
    operator against an ivfflat/HNSW index on resume_chunks.embedding
    (see alembic migration 0002 for the index). This is the path that
    scales to 10,000+ resumes.
  - SQLite (local/dev/test default): brute-force numpy cosine over chunk
    embeddings loaded into memory. Correct, but O(N) -- documented in
    README as a known scale limitation of the zero-dependency dev mode.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import ResumeChunk


@dataclass
class VectorHit:
    chunk_id: str
    candidate_id: str
    resume_id: str
    score: float


async def vector_search(
    db: AsyncSession,
    query_embedding: np.ndarray,
    top_k: int,
    candidate_ids: list[str] | None = None,
    embedding_model: str | None = None,
) -> list[VectorHit]:
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"

    if dialect == "postgresql":
        return await _vector_search_postgres(db, query_embedding, top_k, candidate_ids, embedding_model)
    return await _vector_search_bruteforce(db, query_embedding, top_k, candidate_ids, embedding_model)


async def _vector_search_postgres(
    db: AsyncSession, query_embedding: np.ndarray, top_k: int, candidate_ids: list[str] | None, embedding_model: str | None
):
    from sqlalchemy import text

    vector_literal = "[" + ",".join(f"{x:.6f}" for x in query_embedding.tolist()) + "]"
    filters = []
    params = {"query_vec": vector_literal, "top_k": top_k}
    if candidate_ids:
        filters.append("candidate_id = ANY(:candidate_ids)")
        params["candidate_ids"] = candidate_ids
    if embedding_model:
        filters.append("embedding_model = :embedding_model")
        params["embedding_model"] = embedding_model
    filter_clause = "WHERE " + " AND ".join(filters) if filters else ""

    sql = text(
        f"""
        SELECT id, candidate_id, resume_id, 1 - (embedding <=> :query_vec) AS score
        FROM resume_chunks
        {filter_clause}
        ORDER BY embedding <=> :query_vec
        LIMIT :top_k
        """
    )
    rows = (await db.execute(sql, params)).fetchall()
    return [VectorHit(chunk_id=r.id, candidate_id=r.candidate_id, resume_id=r.resume_id, score=float(r.score)) for r in rows]


async def _vector_search_bruteforce(
    db: AsyncSession, query_embedding: np.ndarray, top_k: int, candidate_ids: list[str] | None, embedding_model: str | None
):
    stmt = select(ResumeChunk).where(ResumeChunk.embedding.is_not(None))
    if candidate_ids:
        stmt = stmt.where(ResumeChunk.candidate_id.in_(candidate_ids))
    if embedding_model:
        stmt = stmt.where(ResumeChunk.embedding_model == embedding_model)
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return []

    matrix = np.array([r.embedding for r in rows], dtype=np.float32)
    query_norm = query_embedding / (np.linalg.norm(query_embedding) or 1.0)
    matrix_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix_norms[matrix_norms == 0] = 1.0
    matrix_normed = matrix / matrix_norms

    sims = matrix_normed @ query_norm
    order = np.argsort(-sims)[:top_k]

    return [
        VectorHit(chunk_id=rows[i].id, candidate_id=rows[i].candidate_id, resume_id=rows[i].resume_id, score=float(sims[i]))
        for i in order
    ]
