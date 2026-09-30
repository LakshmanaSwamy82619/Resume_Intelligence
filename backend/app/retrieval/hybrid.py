"""
Hybrid retrieval orchestration (Section 9) -- the stage that turns
"10,000+ indexed candidates" into a manageable candidate pool for
reranking, per the target architecture:

    Indexed KB -> query understanding -> hybrid retrieval -> candidate pool
    -> reranking -> deep analysis -> final ranking -> Top 3/5

This module deliberately does NOT produce a final ranking. Its only job is
recall: cast a wide net using two independent, differently-biased signals
(lexical TF-IDF + semantic embeddings) plus a structured mandatory-skill /
experience signal, min-max normalize each, blend them, and hand a
generously-sized pool (RETRIEVAL_CANDIDATE_POOL_SIZE) to the reranker.
Precision is the reranker + agents' job (Section 14/16), not this stage's.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.providers.embeddings.chain import EmbeddingProviderChain
from app.retrieval.filters import CandidateMetadata, experience_penalty, mandatory_skill_coverage
from app.retrieval.lexical import lexical_search
from app.retrieval.vector import vector_search

settings = get_settings()


@dataclass
class HybridHit:
    candidate_id: str
    lexical_score: float
    semantic_score: float
    hybrid_score: float
    mandatory_matched: int
    mandatory_total: int
    score_breakdown: dict = field(default_factory=dict)


def _min_max_normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return {k: 0.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


async def hybrid_retrieve(
    db: AsyncSession,
    embedding_chain: EmbeddingProviderChain,
    query_text: str,
    candidate_texts: dict[str, str],
    candidate_metadata: dict[str, CandidateMetadata],
    mandatory_skills: list[str],
    min_years: float | None,
    candidate_id_scope: list[str] | None = None,
    pool_size: int | None = None,
) -> tuple[list[HybridHit], dict]:
    pool_size = pool_size or settings.RETRIEVAL_CANDIDATE_POOL_SIZE
    retrieval_meta: dict = {"lexical_candidates": 0, "semantic_candidates": 0, "semantic_chunk_hits": 0, "embedding_provider": None, "embedding_fallback_used": False, "timings_ms": {}}

    candidate_ids = list(candidate_texts.keys())
    if not candidate_ids:
        return [], retrieval_meta

    # --- Lexical signal ---
    documents = [candidate_texts[cid] for cid in candidate_ids]
    lexical_started = time.perf_counter()
    lexical_hits = lexical_search(query_text, documents)
    retrieval_meta["timings_ms"]["lexical"] = round((time.perf_counter() - lexical_started) * 1000, 2)
    lexical_scores = {candidate_ids[h.doc_index]: h.score for h in lexical_hits}
    retrieval_meta["lexical_candidates"] = sum(1 for s in lexical_scores.values() if s > 0)

    # --- Semantic signal ---
    embedding_started = time.perf_counter()
    query_embedding = await embedding_chain.embed_text(query_text)
    retrieval_meta["timings_ms"]["embedding"] = round((time.perf_counter() - embedding_started) * 1000, 2)
    retrieval_meta["embedding_provider"] = embedding_chain.last_provider_used
    retrieval_meta["embedding_fallback_used"] = embedding_chain.last_fallback_used
    retrieval_meta["embedding_fallback_reason"] = embedding_chain.last_fallback_reason

    vector_started = time.perf_counter()
    vector_hits = await vector_search(
        db,
        query_embedding,
        top_k=max(pool_size * 5, 200),
        candidate_ids=candidate_id_scope or candidate_ids,
        embedding_model=embedding_chain.last_provider_used,
    )
    retrieval_meta["timings_ms"]["semantic_retrieval"] = round((time.perf_counter() - vector_started) * 1000, 2)
    retrieval_meta["semantic_chunk_hits"] = len(vector_hits)
    retrieval_meta["embedding_model"] = embedding_chain.last_provider_used
    semantic_scores: dict[str, float] = {}
    for hit in vector_hits:
        if hit.candidate_id not in semantic_scores or hit.score > semantic_scores[hit.candidate_id]:
            semantic_scores[hit.candidate_id] = hit.score
    retrieval_meta["semantic_candidates"] = len(semantic_scores)

    fusion_started = time.perf_counter()
    norm_lexical = _min_max_normalize(lexical_scores)
    norm_semantic = _min_max_normalize(semantic_scores)

    all_ids = set(candidate_ids)
    hits: list[HybridHit] = []
    for cid in all_ids:
        lex = norm_lexical.get(cid, 0.0)
        sem = norm_semantic.get(cid, 0.0)
        base_score = settings.HYBRID_LEXICAL_WEIGHT * lex + settings.HYBRID_SEMANTIC_WEIGHT * sem

        meta = candidate_metadata.get(cid)
        matched, total = (0, 0)
        penalty = 1.0
        if meta:
            matched, total = mandatory_skill_coverage(meta, mandatory_skills)
            coverage_ratio = (matched / total) if total else 1.0
            penalty = experience_penalty(meta, min_years)
            # Mandatory coverage nudges score rather than hard-filtering, so
            # a strong overall candidate missing one mandatory keyword isn't
            # invisibly dropped (Section 15).
            base_score = base_score * (0.5 + 0.5 * coverage_ratio) * penalty

        hits.append(
            HybridHit(
                candidate_id=cid,
                lexical_score=lex,
                semantic_score=sem,
                hybrid_score=base_score,
                mandatory_matched=matched,
                mandatory_total=total,
                score_breakdown={
                    "raw_lexical": lexical_scores.get(cid, 0.0),
                    "raw_semantic": semantic_scores.get(cid, 0.0),
                    "normalized_lexical": lex,
                    "normalized_semantic": sem,
                    "experience_penalty": penalty,
                },
            )
        )

    hits.sort(key=lambda h: h.hybrid_score, reverse=True)
    retrieval_meta["timings_ms"]["hybrid_fusion"] = round((time.perf_counter() - fusion_started) * 1000, 2)
    return hits[:pool_size], retrieval_meta
