"""
Declarative base + a portable "Vector" column type.

Design note (Section 28/10 trade-off, documented here per Section 42):
    In production (DATABASE_URL pointing at Postgres with the pgvector
    extension enabled) this column compiles to a real `vector(N)` column,
    so similarity search can use pgvector's `<->`/`<=>` operators and an
    ivfflat/HNSW index -- this is what makes 10,000+ resume retrieval fast.

    In local/dev/test mode (SQLite, the zero-dependency default) pgvector
    doesn't exist, so the same column stores the embedding as a JSON array
    and app/retrieval/vector.py falls back to a brute-force numpy cosine
    scan. That is correct but O(N) -- fine for the bundled sample dataset
    and for tests, NOT a substitute for pgvector at real scale. This is
    called out again in README.md's "Known limitations" section.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import TypeDecorator, Text
from sqlalchemy.orm import DeclarativeBase

try:
    from pgvector.sqlalchemy import Vector as _PgVector  # type: ignore

    _HAS_PGVECTOR = True
except Exception:  # pragma: no cover - exercised only when pgvector isn't installed
    _HAS_PGVECTOR = False


class Base(DeclarativeBase):
    pass


class PortableVector(TypeDecorator):
    """A vector column that is a real pgvector column on Postgres and a
    JSON-encoded float list everywhere else (SQLite for local/dev/tests).
    """

    impl = Text
    cache_ok = True

    def __init__(self, dim: int, *args: Any, **kwargs: Any):
        self.dim = dim
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and _HAS_PGVECTOR:
            return dialect.type_descriptor(_PgVector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Optional[list[float]], dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and _HAS_PGVECTOR:
            return value
        return json.dumps([float(x) for x in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and _HAS_PGVECTOR:
            return list(value)
        return json.loads(value)
