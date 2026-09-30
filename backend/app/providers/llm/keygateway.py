"""
KeyGateway LLM provider.

What we actually know about the ArshnivLabs KeyGateway, from the
configuration you supplied and nothing invented beyond it:

    LLM_BASE_URL = https://keygateway1.arshnivlabs.com/v1
    LLM_MODEL    = gpt-4o-mini

The `/v1` suffix and the model name strongly imply an OpenAI-compatible
`/v1/chat/completions` endpoint (this is the standard shape for gateways
that proxy OpenAI-family models), so that is the only endpoint this
provider calls. No other endpoint (embeddings, rerank, fine-tuning, etc.)
is assumed to exist here -- see providers/embeddings and providers/reranker
for how those needs are met without guessing at gateway capabilities that
were never confirmed. If ArshnivLabs documentation later confirms an
`/v1/embeddings` route on the same gateway, KeyGatewayEmbeddingProvider
already implements that OpenAI-compatible call shape and only needs
`EMBEDDING_PROVIDER=keygateway` set to activate it.
"""
from __future__ import annotations

import time

import httpx

from app.core.config import get_settings
from app.providers.llm.base import LLMProvider, LLMResult, ProviderCallFailed

settings = get_settings()


class KeyGatewayLLMProvider(LLMProvider):
    name = "keygateway"

    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.max_retries = settings.LLM_MAX_RETRIES

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2, max_tokens: int = 800) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = f"{self.base_url}/chat/completions"
        start = time.perf_counter()
        last_error: str | None = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(url, headers=self._headers(), json=payload)
                    response.raise_for_status()
                    data = response.json()
                    text = data["choices"][0]["message"]["content"]
                    latency_ms = (time.perf_counter() - start) * 1000
                    return LLMResult(
                        text=text,
                        provider=self.name,
                        model_used=data.get("model", self.model),
                        fallback_used=False,
                        latency_ms=latency_ms,
                        raw=data,
                    )
                except (httpx.HTTPStatusError, httpx.RequestError, KeyError, ValueError) as exc:
                    last_error = str(exc)
                    if attempt < self.max_retries:
                        # controlled backoff, not an infinite retry loop
                        import asyncio

                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue

        raise ProviderCallFailed(self.name, last_error or "unknown error")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                return resp.status_code < 500
        except Exception:
            return False
