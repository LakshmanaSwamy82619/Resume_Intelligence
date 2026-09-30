from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class EmbeddingProviderFailed(Exception):
    def __init__(self, provider: str, reason: str):
        super().__init__(f"{provider} failed: {reason}")
        self.provider = provider
        self.reason = reason


class EmbeddingProvider(ABC):
    name: str = "base"
    dimension: int = 0

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Return an (N, dim) L2-normalized float32 matrix."""
        ...

    async def embed_text(self, text: str) -> np.ndarray:
        result = await self.embed_texts([text])
        return result[0]
