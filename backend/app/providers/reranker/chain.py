from __future__ import annotations

import logging

from app.core.config import get_settings
from app.providers.reranker.base import RerankerProvider, RerankerProviderFailed
from app.providers.reranker.local import CrossEncoderRerankerProvider, HeuristicRerankerProvider

logger = logging.getLogger("app.providers.reranker")
settings = get_settings()


class RerankerProviderChain:
    def __init__(self):
        self.primary: RerankerProvider = CrossEncoderRerankerProvider()
        self.fallback: RerankerProvider = HeuristicRerankerProvider()
        self.last_provider_used = self.primary.name
        self.last_fallback_used = False
        self.last_fallback_reason: str | None = None

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        if settings.RERANKER_PROVIDER == "none" or not documents:
            self.last_provider_used = "none"
            self.last_fallback_used = False
            self.last_fallback_reason = None
            return [0.0 for _ in documents]
        try:
            scores = await self.primary.rerank(query, documents)
            self.last_provider_used = self.primary.name
            self.last_fallback_used = False
            self.last_fallback_reason = None
            return scores
        except RerankerProviderFailed as exc:
            logger.warning(
                "reranker_provider_failed_falling_back",
                extra={"extra_fields": {"provider": exc.provider, "reason": exc.reason}},
            )
            scores = await self.fallback.rerank(query, documents)
            self.last_provider_used = self.fallback.name
            self.last_fallback_used = True
            self.last_fallback_reason = exc.reason
            return scores


_shared_chain: RerankerProviderChain | None = None


def get_reranker_provider_chain() -> RerankerProviderChain:
    global _shared_chain
    if _shared_chain is None:
        _shared_chain = RerankerProviderChain()
    return _shared_chain
