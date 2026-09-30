from __future__ import annotations

import pytest

from app.providers.llm.base import LLMProvider, LLMResult, ProviderCallFailed
from app.providers.llm.chain import LLMProviderChain
from app.providers.reranker.base import RerankerProvider, RerankerProviderFailed
from app.providers.reranker.chain import RerankerProviderChain
from app.providers.reranker.local import HeuristicRerankerProvider


class FixedReranker(RerankerProvider):
    def __init__(self, name: str, scores: list[float], fail: bool = False):
        self.name = name
        self.scores = scores
        self.fail = fail

    async def rerank(self, _query: str, _documents: list[str]) -> list[float]:
        if self.fail:
            raise RerankerProviderFailed(self.name, "test failure")
        return self.scores


@pytest.mark.asyncio
async def test_real_heuristic_reranker_orders_keyword_overlap():
    scores = await HeuristicRerankerProvider().rerank(
        "python sql",
        ["JavaScript frontend components", "Python and SQL data pipeline experience"],
    )
    assert scores[1] > scores[0]


@pytest.mark.asyncio
async def test_reranker_fallback_is_reported_and_recovers(monkeypatch):
    from app.providers.reranker import chain as reranker_module

    monkeypatch.setattr(reranker_module.settings, "RERANKER_PROVIDER", "local")
    chain = RerankerProviderChain()
    primary = FixedReranker("cross-encoder-test", [0.9], fail=True)
    chain.primary = primary
    chain.fallback = FixedReranker("heuristic-test", [0.4])

    assert await chain.rerank("python", ["python experience"]) == [0.4]
    assert chain.last_provider_used == "heuristic-test"
    assert chain.last_fallback_used is True
    assert chain.last_fallback_reason == "test failure"

    primary.fail = False
    assert await chain.rerank("python", ["python experience"]) == [0.9]
    assert chain.last_provider_used == "cross-encoder-test"
    assert chain.last_fallback_used is False
    assert chain.last_fallback_reason is None


class FailedLLM(LLMProvider):
    name = "external-test"

    async def complete(self, *_args, **_kwargs):
        raise ProviderCallFailed(self.name, "service unavailable")

    async def health_check(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_llm_provider_failure_uses_deterministic_explanation():
    chain = LLMProviderChain(providers=[FailedLLM()])
    result = await chain.complete(
        "system",
        "request",
        deterministic_fallback_kwargs={
            "candidate_name": "Casey",
            "matched": [{"requirement": "Python"}],
            "partial": [],
            "missing": [],
            "years_of_experience": None,
            "top_evidence": [{"evidence_text": "Used Python in a project.", "source_file": "casey.pdf", "page_number": 1}],
        },
    )
    assert result.provider == "deterministic"
    assert result.fallback_used is True
    assert "Python" in result.text
    assert "service unavailable" in result.fallback_reason


@pytest.mark.asyncio
async def test_deterministic_fallback_without_llm_provider_is_explicit():
    result = await LLMProviderChain(providers=[]).complete(
        "system",
        "request",
        deterministic_fallback_kwargs={
            "candidate_name": "Casey",
            "matched": [],
            "partial": [],
            "missing": [],
            "years_of_experience": None,
            "top_evidence": [],
        },
    )
    assert result.provider == "deterministic"
    assert result.fallback_used is True
    assert result.fallback_reason == "no LLM provider configured"


def test_configured_openai_provider_uses_existing_openai_compatible_transport(monkeypatch):
    from app.providers.llm import chain as llm_chain_module
    from app.providers.llm.openai import OpenAILLMProvider

    monkeypatch.setattr(llm_chain_module.settings, "LLM_PROVIDER", "openai")
    chain = LLMProviderChain()

    assert len(chain.providers) == 1
    assert isinstance(chain.providers[0], OpenAILLMProvider)
    assert chain.providers[0].name == "openai"
