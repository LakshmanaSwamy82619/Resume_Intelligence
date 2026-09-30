from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.ingestion.dataset_import import import_dataset
from app.models.candidate import Resume, ResumeChunk

pytestmark = pytest.mark.asyncio


class MockEmbeddingChain:
    last_provider_used = "test-hash-mock"
    last_fallback_used = True
    last_fallback_reason = "mocked offline provider"

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), get_settings().VECTOR_DIMENSION), dtype=np.float32)
        vectors[:, 0] = 1.0
        return vectors


async def test_dataset_import_persists_provenance_and_reports_failures(client, hr_token, tmp_path):
    data_dir = tmp_path / "dataset"
    category_dir = data_dir / "ENGINEERING"
    category_dir.mkdir(parents=True)
    (category_dir / "candidate.txt").write_text(
        "Taylor Engineer\ntaylor.engineer@example.com\nSkills\nPython, SQL\nExperience\nData Engineer at Acme",
        encoding="utf-8",
    )
    (category_dir / "broken.pdf").write_bytes(b"not a pdf")
    (data_dir / "Resume.csv").write_text("ID,Category\n", encoding="utf-8")

    async with AsyncSessionLocal() as db:
        summary = await import_dataset(db, data_dir, embedding_chain=MockEmbeddingChain())
        repeated = await import_dataset(db, data_dir, embedding_chain=MockEmbeddingChain())
        stored = (await db.execute(select(Resume).where(Resume.original_filename == "candidate.txt"))).scalar_one()
        chunks = (await db.execute(select(ResumeChunk).where(ResumeChunk.resume_id == stored.id))).scalars().all()

    assert summary["discovered"] == 2
    assert summary["imported"] == 1
    assert summary["failed"] == 1
    assert summary["errors"][0]["source"] == "ENGINEERING/broken.pdf"
    assert repeated["duplicates"] == 1
    assert stored.source_category == "ENGINEERING"
    assert stored.source_relative_path == "ENGINEERING/candidate.txt"
    assert stored.processing_status == "completed"
    assert chunks and all(chunk.embedding is not None for chunk in chunks)
    assert all(chunk.embedding_model == "test-hash-mock" for chunk in chunks)

    headers = {"Authorization": f"Bearer {hr_token}"}
    listed = await client.get("/api/v1/candidates?page=1&page_size=100", headers=headers)
    item = next(row for row in listed.json()["items"] if row["candidate_id"] == stored.candidate_id)
    assert item["category"] == "ENGINEERING"
    assert item["source_filename"] == "candidate.txt"
    detail = await client.get(f"/api/v1/resumes/candidates/{stored.candidate_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["category"] == "ENGINEERING"
    assert detail.json()["resumes"][0]["category"] == "ENGINEERING"
    assert detail.json()["resumes"][0]["processing_status"] == "completed"
    assert "source_relative_path" not in detail.json()

    unauthenticated = await client.get("/api/v1/candidates?page=1&page_size=1")
    assert unauthenticated.status_code == 401
