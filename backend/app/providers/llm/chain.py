"""
LLM fallback chain (Section 12/33).

    Primary (KeyGateway)
      -> controlled retry with backoff (handled inside the provider itself)
      -> secondary provider, if configured
      -> deterministic, evidence-only explanation (never fails, never network)

`complete_with_fallback` always returns an LLMResult; it never raises, so
callers (the Explainability Agent) can always produce a response even if
every network provider is down. Callers get `fallback_used` /
`fallback_reason` / `provider` on the result so the API layer can surface
`ai_provider` / `fallback_used` / `processing_mode` per Section 33.
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.providers.llm.base import LLMProvider, LLMResult, ProviderCallFailed
from app.providers.llm.deterministic import build_deterministic_explanation
from app.providers.llm.keygateway import KeyGatewayLLMProvider
from app.providers.llm.openai import OpenAILLMProvider

logger = logging.getLogger("app.providers.llm")
settings = get_settings()


class LLMProviderChain:
    def __init__(self, providers: list[LLMProvider] | None = None):
        self.providers = providers if providers is not None else self._build_default_chain()

    def _build_default_chain(self) -> list[LLMProvider]:
        chain: list[LLMProvider] = []
        if settings.LLM_PROVIDER == "openai":
            chain.append(OpenAILLMProvider())
        elif settings.LLM_PROVIDER == "keygateway":
            chain.append(KeyGatewayLLMProvider())
        # A LocalLLMProvider (e.g. an on-box small model via llama.cpp/Ollama)
        # could be appended here when settings.LLM_FALLBACK_PROVIDER == "local".
        # We do not fabricate one: no local LLM runtime is bundled in this
        # environment, so the honest fallback below deterministic templates.
        return chain

    async def complete(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2, max_tokens: int = 800,
                        deterministic_fallback_kwargs: dict | None = None) -> LLMResult:
        last_reason = "no LLM provider configured"
        for provider in self.providers:
            try:
                return await provider.complete(system_prompt, user_prompt, temperature=temperature, max_tokens=max_tokens)
            except ProviderCallFailed as exc:
                last_reason = f"{exc.provider}: {exc.reason}"
                logger.warning("llm_provider_failed", extra={"extra_fields": {"provider": exc.provider, "reason": exc.reason}})
                continue
            except Exception as exc:  # defensive: never let a provider bug break candidate selection
                last_reason = f"{provider.name}: unexpected error {exc}"
                logger.exception("llm_provider_unexpected_error")
                continue

        # Every network provider failed (or none configured) -> deterministic.
        if deterministic_fallback_kwargs is not None:
            result = build_deterministic_explanation(**deterministic_fallback_kwargs)
            result.fallback_reason = last_reason
            return result

        return LLMResult(
            text="",
            provider="deterministic",
            model_used=None,
            fallback_used=True,
            fallback_reason=last_reason,
        )
