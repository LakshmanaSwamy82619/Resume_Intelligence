"""
KeyGateway embedding provider.

IMPORTANT (Section 11): the gateway configuration you gave us only
confirms a chat-completions-shaped endpoint. There is no confirmed
`/v1/embeddings` route on `keygateway1.arshnivlabs.com` -- we found no
public documentation for this gateway either. This class implements the
standard OpenAI-compatible embeddings call shape *in case* that route
exists, but it is NOT wired up as the default (`EMBEDDING_PROVIDER=local`
in .env.example). Do not enable `EMBEDDING_PROVIDER=keygateway` in
production until you've confirmed the endpoint responds -- otherwise every
embedding call will fail over to the hashing fallback and retrieval
quality will silently degrade to lexical-only. `health_check()` below is
the way to confirm it before flipping the switch.
"""
from __future__ import annotations

import numpy as np
import httpx

from app.core.config import get_settings
from app.providers.embeddings.base import EmbeddingProvider, EmbeddingProviderFailed

settings = get_settings()


class KeyGatewayEmbeddingProvider(EmbeddingProvider):
    name = "keygateway"

    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.VECTOR_DIMENSION
        self.name = f"keygateway:{self.model}:dim={self.dimension}"

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        url = f"{self.base_url}/embeddings"
        payload = {"model": self.model, "input": texts}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
                vectors = [item["embedding"] for item in data["data"]]
        except Exception as exc:
            raise EmbeddingProviderFailed(self.name, f"embeddings endpoint call failed (unconfirmed route): {exc}")

        arr = np.array(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    async def health_check(self) -> bool:
        try:
            await self.embed_texts(["healthcheck"])
            return True
        except EmbeddingProviderFailed:
            return False
