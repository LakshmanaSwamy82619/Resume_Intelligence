from __future__ import annotations

import numpy as np
import pytest
import sys
from types import ModuleType

from app.db.session import AsyncSessionLocal, init_models
from app.models.candidate import Candidate, Resume, ResumeChunk
from app.providers.embeddings.base import EmbeddingProvider, EmbeddingProviderFailed
from app.providers.embeddings.chain import EmbeddingProviderChain
from app.retrieval.vector import vector_search


def test_local_model_load_failure_is_cached_for_batch_fallback(monkeypatch):
    from app.providers.embeddings import local

    attempts = []
    fake_transformers = ModuleType("sentence_transformers")

    class MissingModel:
        def __init__(self, _name):
            attempts.append(1)
            raise OSError("offline")

    fake_transformers.SentenceTransformer = MissingModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_transformers)
    monkeypatch.setattr(local, "_st_model", None)
    monkeypatch.setattr(local, "_st_load_error", None)
    provider = local.LocalEmbeddingProvider("missing-model")

    for _ in range(2):
        with pytest.raises(EmbeddingProviderFailed):
            provider._get_model()

    assert len(attempts) == 1


class FixedEmbedding(EmbeddingProvider):
    def __init__(self, name: str, dimension: int, fail: bool = False):
        self.name = name
        self.dimension = dimension
        self.fail = fail

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        if self.fail:
            raise EmbeddingProviderFailed(self.name, "test failure")
        return np.ones((len(texts), self.dimension), dtype=np.float32)


@pytest.mark.asyncio
async def test_primary_embedding_reports_its_model_identity():
    chain = EmbeddingProviderChain()
    chain.primary = FixedEmbedding("primary-model:v1:dim=384", 384)
    chain.fallback = FixedEmbedding("hashing-v1:dim=384", 384)

    vectors = await chain.embed_texts(["candidate text"])
    assert vectors.shape == (1, 384)
    assert chain.last_provider_used == "primary-model:v1:dim=384"
    assert chain.last_fallback_used is False


@pytest.mark.asyncio
async def test_failed_primary_uses_identified_fallback_and_recovers():
    chain = EmbeddingProviderChain()
    primary = FixedEmbedding("primary-model:v1:dim=384", 384, fail=True)
    chain.primary = primary
    chain.fallback = FixedEmbedding("hashing-v1:dim=384", 384)

    await chain.embed_texts(["first"])
    assert chain.last_provider_used == "hashing-v1:dim=384"
    assert chain.last_fallback_used is True
    assert chain.last_fallback_reason == "test failure"

    primary.fail = False
    await chain.embed_texts(["recovered"])
    assert chain.last_provider_used == "primary-model:v1:dim=384"
    assert chain.last_fallback_used is False
    assert chain.last_fallback_reason is None


@pytest.mark.asyncio
async def test_wrong_primary_embedding_dimension_uses_fallback():
    chain = EmbeddingProviderChain()
    chain.primary = FixedEmbedding("wrong-dimension", 384)
    chain.primary.embed_texts = lambda texts: _wrong_dimensions(len(texts))
    chain.fallback = FixedEmbedding("hashing-v1:dim=384", 384)
    vectors = await chain.embed_texts(["candidate text"])
    assert vectors.shape == (1, 384)
    assert chain.last_provider_used == "hashing-v1:dim=384"
    assert chain.last_fallback_used is True


async def _wrong_dimensions(count: int) -> np.ndarray:
    return np.ones((count, 3), dtype=np.float32)


@pytest.mark.asyncio
async def test_vector_search_excludes_incompatible_embedding_models():
    await init_models()
    async with AsyncSessionLocal() as db:
        candidate = Candidate(full_name="Vector Fixture", technical_skills=[], soft_skills=[], job_titles=[])
        db.add(candidate)
        await db.flush()
        resume = Resume(
            candidate_id=candidate.id,
            original_filename="fixture.txt",
            storage_path="unused",
            mime_type="text/plain",
            file_size_bytes=1,
            file_hash=f"vector-test-{candidate.id}",
        )
        db.add(resume)
        await db.flush()
        preferred = np.zeros(384, dtype=np.float32)
        preferred[0] = 1.0
        incompatible = np.zeros(384, dtype=np.float32)
        incompatible[1] = 1.0
        db.add_all(
            [
                ResumeChunk(
                    resume_id=resume.id,
                    candidate_id=candidate.id,
                    chunk_index=0,
                    text="compatible vector",
                    embedding=preferred.tolist(),
                    embedding_model="primary-model:v1:dim=384",
                ),
                ResumeChunk(
                    resume_id=resume.id,
                    candidate_id=candidate.id,
                    chunk_index=1,
                    text="incompatible vector",
                    embedding=incompatible.tolist(),
                    embedding_model="hashing-vectorizer-v1:dim=384",
                ),
            ]
        )
        await db.commit()

        hits = await vector_search(
            db,
            preferred,
            top_k=10,
            candidate_ids=[candidate.id],
            embedding_model="primary-model:v1:dim=384",
        )
        assert len(hits) == 1
        assert hits[0].score == pytest.approx(1.0)
