"""
Evaluation metrics (Section 22/23).

Every function here computes a metric FROM ACTUAL DATA passed in -- labels
from a human-curated EvaluationDataset, or evidence/claims produced by a
real search run. Nothing here invents a score (Section 46): if there is no
labelled dataset yet, `evaluate_dataset` in runner.py simply has nothing to
compute against, and the API returns an empty/zero result with a message
saying so, not a fabricated number.
"""
from __future__ import annotations

import math


def precision_at_k(ranked_candidate_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = ranked_candidate_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for cid in top_k if cid in relevant_ids)
    return hits / len(top_k)


def recall_at_k(ranked_candidate_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = ranked_candidate_ids[:k]
    hits = sum(1 for cid in top_k if cid in relevant_ids)
    return hits / len(relevant_ids)


def mean_reciprocal_rank(ranked_candidate_ids: list[str], relevant_ids: set[str]) -> float:
    for i, cid in enumerate(ranked_candidate_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / i
    return 0.0


def dcg_at_k(ranked_relevances: list[int], k: int) -> float:
    total = 0.0
    for i, rel in enumerate(ranked_relevances[:k], start=1):
        total += (2**rel - 1) / math.log2(i + 1)
    return total


def ndcg_at_k(ranked_candidate_ids: list[str], relevance_map: dict[str, int], k: int) -> float:
    ranked_relevances = [relevance_map.get(cid, 0) for cid in ranked_candidate_ids]
    ideal_relevances = sorted(relevance_map.values(), reverse=True)
    actual_dcg = dcg_at_k(ranked_relevances, k)
    ideal_dcg = dcg_at_k(ideal_relevances, k)
    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def skill_matching_accuracy(predicted_matched: set[str], predicted_missing: set[str], ground_truth_present: set[str]) -> dict:
    """Compares the system's matched/missing skill calls against a
    human-verified 'skills actually present in this resume' set for one
    candidate. Returns precision/recall/F1 for the 'matched' call.
    """
    predicted_present = predicted_matched
    tp = len(predicted_present & ground_truth_present)
    fp = len(predicted_present - ground_truth_present)
    fn = len(ground_truth_present - predicted_present)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def evidence_grounding_rate(findings_with_evidence: int, total_findings: int) -> float:
    if total_findings == 0:
        return 1.0
    return round(findings_with_evidence / total_findings, 4)


def unsupported_claim_rate(flagged_claims: int, total_claims: int) -> float:
    if total_claims == 0:
        return 0.0
    return round(flagged_claims / total_claims, 4)
