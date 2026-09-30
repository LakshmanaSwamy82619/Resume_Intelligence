from __future__ import annotations

from abc import ABC, abstractmethod


class RerankerProviderFailed(Exception):
    def __init__(self, provider: str, reason: str):
        super().__init__(f"{provider} failed: {reason}")
        self.provider = provider
        self.reason = reason


class RerankerProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Return one relevance score per document, same order as input."""
        ...
