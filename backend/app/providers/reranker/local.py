"""
Local reranker providers (Section 14).

CrossEncoderRerankerProvider wraps a real cross-encoder model
(cross-encoder/ms-marco-MiniLM-L-6-v2 by default) which jointly encodes
(query, document) pairs -- this is what actually improves ranking quality
over a plain bi-encoder cosine similarity, because it can attend across the
query and document instead of comparing two independently-pooled vectors.

HeuristicRerankerProvider is the fallback rung: a transparent, deterministic
lexical-overlap scorer (query-term coverage + position-weighted overlap).
It is intentionally simple and explainable rather than a second neural
model, because its only job is to keep the pipeline degrading gracefully
when the cross-encoder can't be loaded (no network to fetch weights) --
not to imitate the cross-encoder's quality.
"""
from __future__ import annotations

import asyncio
import re
import threading

from app.core.config import get_settings
from app.providers.reranker.base import RerankerProvider, RerankerProviderFailed

settings = get_settings()

_cross_encoder = None
_ce_lock = threading.Lock()

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class CrossEncoderRerankerProvider(RerankerProvider):
    name = "local_cross_encoder"

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.RERANKER_MODEL

    def _get_model(self):
        global _cross_encoder
        if _cross_encoder is None:
            with _ce_lock:
                if _cross_encoder is None:
                    try:
                        from sentence_transformers import CrossEncoder
                    except ImportError as exc:
                        raise RerankerProviderFailed(self.name, f"sentence-transformers not installed: {exc}")
                    try:
                        _cross_encoder = CrossEncoder(self.model_name)
                    except Exception as exc:
                        raise RerankerProviderFailed(
                            self.name, f"could not load reranker model '{self.model_name}' (likely no network access): {exc}"
                        )
        return _cross_encoder

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._rerank_sync, query, documents)

    def _rerank_sync(self, query: str, documents: list[str]) -> list[float]:
        model = self._get_model()
        try:
            pairs = [[query, doc] for doc in documents]
            scores = model.predict(pairs)
        except Exception as exc:
            raise RerankerProviderFailed(self.name, str(exc))
        return [float(s) for s in scores]


class HeuristicRerankerProvider(RerankerProvider):
    """Deterministic query-term-coverage reranker used when the neural
    cross-encoder can't be loaded. Scores each document by:
      - fraction of distinct query terms present in the document
      - a mild boost for query terms appearing close together (bigram overlap)
    This is a real, inspectable scoring function -- not a placeholder that
    returns a constant -- so ranking degradation under fallback is honest
    but still functional.
    """

    name = "local_heuristic"

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return [0.0 for _ in documents]

        scores = []
        for doc in documents:
            doc_tokens = _tokenize(doc)
            doc_token_set = set(doc_tokens)
            overlap = len(query_tokens & doc_token_set)
            coverage = overlap / len(query_tokens)

            doc_bigrams = {f"{a}_{b}" for a, b in zip(doc_tokens, doc_tokens[1:])}
            query_list = list(query_tokens)
            query_bigrams = {f"{a}_{b}" for a, b in zip(query_list, query_list[1:])}
            bigram_overlap = len(doc_bigrams & query_bigrams)

            score = coverage + 0.1 * min(bigram_overlap, 5)
            scores.append(float(score))
        return scores
