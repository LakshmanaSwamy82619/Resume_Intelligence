"""
Local embedding providers.

LocalEmbeddingProvider wraps `sentence-transformers` (default model:
all-MiniLM-L6-v2, 384-dim) -- a real neural sentence encoder that captures
semantic similarity, run entirely on-box so the system is not dependent on
an external embeddings API (Section 10).

HashingEmbeddingProvider is the fallback rung underneath it. It is NOT a
semantic model -- it is a deterministic hashed bag-of-words / TF-IDF-style
vectorizer (scikit-learn's HashingVectorizer). It exists purely so that
retrieval keeps working (on lexical/token overlap) in an environment where
the neural model cannot be downloaded or loaded, per Section 13's
requirement that ML fallback must not be a single point of failure. This
is deliberately labelled as a *lexical* approximation, not a substitute for
real semantic embeddings -- see README "Known limitations".
"""
from __future__ import annotations

import asyncio
import threading

import numpy as np

from app.core.config import get_settings
from app.providers.embeddings.base import EmbeddingProvider, EmbeddingProviderFailed

settings = get_settings()

_st_model = None
_st_load_error: str | None = None
_st_lock = threading.Lock()


class LocalEmbeddingProvider(EmbeddingProvider):
    name = "local_sentence_transformers"

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.dimension = settings.VECTOR_DIMENSION
        self.name = f"sentence-transformers:{self.model_name}:dim={self.dimension}"

    def _get_model(self):
        global _st_model, _st_load_error
        if _st_model is None:
            with _st_lock:
                if _st_model is None:
                    if _st_load_error is not None:
                        raise EmbeddingProviderFailed(self.name, _st_load_error)
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:
                        raise EmbeddingProviderFailed(self.name, f"sentence-transformers not installed: {exc}")
                    try:
                        _st_model = SentenceTransformer(self.model_name)
                    except Exception as exc:
                        _st_load_error = (
                            f"could not load model '{self.model_name}' "
                            f"(likely no network access to download it): {exc}"
                        )
                        raise EmbeddingProviderFailed(self.name, _st_load_error) from exc
        return _st_model

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> np.ndarray:
        model = self._get_model()
        try:
            embeddings = model.encode(
                texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True, convert_to_numpy=True
            )
        except Exception as exc:
            raise EmbeddingProviderFailed(self.name, str(exc))
        return embeddings.astype(np.float32)


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic, offline, no-download fallback. Uses the hashing trick
    so vocabulary size is unbounded but the feature space is fixed at
    settings.VECTOR_DIMENSION, then L2-normalizes so downstream cosine
    similarity is a plain dot product, matching LocalEmbeddingProvider's
    contract.
    """

    name = "local_hashing"

    def __init__(self, dim: int | None = None):
        self.dimension = dim or settings.VECTOR_DIMENSION
        self.name = f"hashing-vectorizer-v1:dim={self.dimension}"
        from sklearn.feature_extraction.text import HashingVectorizer

        self._vectorizer = HashingVectorizer(
            n_features=self.dimension,
            alternate_sign=True,
            norm="l2",
            ngram_range=(1, 2),
            lowercase=True,
        )

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> np.ndarray:
        matrix = self._vectorizer.transform(texts)
        dense = matrix.toarray().astype(np.float32)
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return dense / norms
