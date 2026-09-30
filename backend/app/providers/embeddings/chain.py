from __future__ import annotations

import logging

import numpy as np

from app.core.config import get_settings
from app.providers.embeddings.base import EmbeddingProvider, EmbeddingProviderFailed
from app.providers.embeddings.keygateway import KeyGatewayEmbeddingProvider
from app.providers.embeddings.local import HashingEmbeddingProvider, LocalEmbeddingProvider

logger = logging.getLogger("app.providers.embeddings")
settings = get_settings()


class EmbeddingProviderChain:
    """Primary embedding provider (per EMBEDDING_PROVIDER) with an offline
    hashing fallback (Section 10/13). Also exposes `last_provider_used` and
    `last_fallback_used` so callers (ingestion/search) can record which
    embedding space a given vector was produced in -- important because
    vectors from different providers/dimensions are not comparable.
    """

    def __init__(self):
        self.primary: EmbeddingProvider = self._build_primary()
        self.fallback: EmbeddingProvider = HashingEmbeddingProvider(dim=settings.VECTOR_DIMENSION)
        self.last_provider_used: str = self.primary.name
        self.last_fallback_used: bool = False
        self.last_fallback_reason: str | None = None

    def _build_primary(self) -> EmbeddingProvider:
        if settings.EMBEDDING_PROVIDER == "keygateway":
            return KeyGatewayEmbeddingProvider()
        return LocalEmbeddingProvider()

    @staticmethod
    def _validate_vectors(vectors: np.ndarray, text_count: int, provider: EmbeddingProvider) -> np.ndarray:
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != text_count or vectors.shape[1] != settings.VECTOR_DIMENSION:
            raise EmbeddingProviderFailed(
                provider.name,
                f"expected ({text_count}, {settings.VECTOR_DIMENSION}) embeddings; received {vectors.shape}",
            )
        return vectors

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        try:
            vectors = self._validate_vectors(await self.primary.embed_texts(texts), len(texts), self.primary)
            self.last_provider_used = self.primary.name
            self.last_fallback_used = False
            self.last_fallback_reason = None
            return vectors
        except EmbeddingProviderFailed as exc:
            logger.warning(
                "embedding_provider_failed_falling_back",
                extra={"extra_fields": {"provider": exc.provider, "reason": exc.reason}},
            )
            vectors = self._validate_vectors(await self.fallback.embed_texts(texts), len(texts), self.fallback)
            self.last_provider_used = self.fallback.name
            self.last_fallback_used = True
            self.last_fallback_reason = exc.reason
            return vectors

    async def embed_text(self, text: str) -> np.ndarray:
        result = await self.embed_texts([text])
        return result[0]


_shared_chain: EmbeddingProviderChain | None = None


def get_embedding_provider_chain() -> EmbeddingProviderChain:
    global _shared_chain
    if _shared_chain is None:
        _shared_chain = EmbeddingProviderChain()
    return _shared_chain
