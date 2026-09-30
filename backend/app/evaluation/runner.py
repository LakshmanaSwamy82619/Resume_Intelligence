"""
Evaluation runner (Section 22/23).

Runs the ACTUAL search pipeline (same code path as a real HR search) for
every query in a labelled EvaluationDataset, then scores the results
against the human relevance labels. No metric here is invented; a dataset
with zero labelled queries simply produces zero-length per_query_results
and a metrics dict noting that no labels were available.
"""
from __future__ import annotations

from app.evaluation.dataset import get_dataset_with_queries
from app.evaluation.metrics import mean_reciprocal_rank, ndcg_at_k, precision_at_k, recall_at_k
from app.models.search import EvaluationResult
from app.models.candidate import ResumeEvidence
from sqlalchemy import select
from app.services.search_service import run_search
from sqlalchemy.ext.asyncio import AsyncSession


async def run_evaluation(db: AsyncSession, dataset_id: str, top_n: int, triggered_by_user_id: str) -> EvaluationResult:
    dataset = await get_dataset_with_queries(db, dataset_id)
    if dataset is None:
        raise ValueError("Evaluation dataset not found.")

    per_query_results = []
    precisions, recalls, mrrs, ndcgs = [], [], [], []
    skill_confusion = {label: {pred: 0 for pred in ("matched", "partial", "missing")} for label in ("matched", "partial", "missing")}
    skill_items = 0
    evidence_claims = grounded_claims = flagged_candidates = evaluated_candidates = 0

    for query in dataset.queries:
        relevance_map = {label.candidate_id: label.relevance for label in query.labels}
        relevant_ids = {cid for cid, rel in relevance_map.items() if rel >= 1}

        if not relevance_map:
            per_query_results.append({"query": query.query_text, "note": "No human labels for this query; skipped."})
            continue

        try:
            search = await run_search(db, hr_user_id=triggered_by_user_id, query_text=query.query_text, job=None, top_n=top_n)
        except Exception as exc:
            per_query_results.append({"query": query.query_text, "error": str(exc)})
            continue

        ranked_ids = [sc.candidate_id for sc in sorted(search.candidates, key=lambda c: c.rank)]
        candidates = {sc.candidate_id: sc for sc in search.candidates}
        evaluated_candidates += len(search.candidates)
        candidate_ids = list(candidates)
        evidence_rows = (await db.execute(select(ResumeEvidence).where(ResumeEvidence.candidate_id.in_(candidate_ids)))).scalars().all() if candidate_ids else []
        evidence_by_candidate: dict[str, list[str]] = {}
        for ev in evidence_rows:
            evidence_by_candidate.setdefault(ev.candidate_id, []).append(" ".join(ev.evidence_text.casefold().split()))

        query_skill_correct = query_skill_count = query_claims = query_grounded = 0
        for label in query.labels:
            for skill, expected in (label.skill_statuses or {}).items():
                skill_key = " ".join(skill.casefold().split())
                candidate = candidates.get(label.candidate_id)
                predicted = "missing"
                if candidate:
                    findings = [*candidate.matched_requirements, *candidate.partial_requirements, *candidate.missing_requirements]
                    match = next((f for f in findings if " ".join(str(f.get("requirement", "")).casefold().split()) == skill_key and f.get("requirement_type") in {"skill", "technology"}), None)
                    if match:
                        predicted = "matched" if match.get("status") == "matched" else "partial" if match.get("status") == "partial" else "missing"
                skill_confusion[expected][predicted] += 1
                skill_items += 1
                query_skill_count += 1
                query_skill_correct += int(predicted == expected)

        for candidate in search.candidates:
            if candidate.validation_status == "flagged":
                flagged_candidates += 1
            for finding in [*candidate.matched_requirements, *candidate.partial_requirements]:
                query_claims += 1
                snippet = " ".join(str(finding.get("evidence_text") or "").casefold().split())
                grounded = bool(snippet) and any(snippet in source for source in evidence_by_candidate.get(candidate.candidate_id, []))
                if grounded:
                    query_grounded += 1
        evidence_claims += query_claims
        grounded_claims += query_grounded

        p = precision_at_k(ranked_ids, relevant_ids, top_n)
        r = recall_at_k(ranked_ids, relevant_ids, top_n)
        mrr = mean_reciprocal_rank(ranked_ids, relevant_ids)
        ndcg = ndcg_at_k(ranked_ids, relevance_map, top_n)

        precisions.append(p)
        recalls.append(r)
        mrrs.append(mrr)
        ndcgs.append(ndcg)

        per_query_results.append(
            {
                "query": query.query_text,
                "ranked_candidate_ids": ranked_ids,
                "relevant_candidate_ids": list(relevant_ids),
                f"precision_at_{top_n}": p,
                f"recall_at_{top_n}": r,
                "mrr": mrr,
                f"ndcg_at_{top_n}": ndcg,
                "fallback_used": search.fallback_used,
                "skill_status_items": query_skill_count,
                "skill_status_accuracy": round(query_skill_correct / query_skill_count, 4) if query_skill_count else None,
                "evidence_claims_checked": query_claims,
                "evidence_grounded_claims": query_grounded,
                "evidence_grounding_rate": round(query_grounded / query_claims, 4) if query_claims else None,
            }
        )

    def _avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    skill_class_metrics = {}
    for label, predictions in skill_confusion.items():
        true_positive = predictions[label]
        predicted_count = sum(skill_confusion[actual][label] for actual in skill_confusion)
        actual_count = sum(predictions.values())
        precision = true_positive / predicted_count if predicted_count else None
        recall = true_positive / actual_count if actual_count else None
        precision_for_f1 = precision or 0.0
        recall_for_f1 = recall or 0.0
        f1 = (2 * precision_for_f1 * recall_for_f1 / (precision_for_f1 + recall_for_f1)) if (predicted_count or actual_count) and precision_for_f1 + recall_for_f1 else 0.0 if (predicted_count or actual_count) else None
        skill_class_metrics[label] = {
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }
    defined_f1 = [values["f1"] for values in skill_class_metrics.values() if values["f1"] is not None]

    metrics = {
        "queries_evaluated": len(precisions),
        "queries_skipped_no_labels": sum(1 for r in per_query_results if r.get("note")),
        f"avg_precision_at_{top_n}": _avg(precisions),
        f"avg_recall_at_{top_n}": _avg(recalls),
        "avg_mrr": _avg(mrrs),
        f"avg_ndcg_at_{top_n}": _avg(ndcgs),
        "skill_gap_labeled_items": skill_items,
        "skill_gap_accuracy": round(sum(skill_confusion[label][label] for label in skill_confusion) / skill_items, 4) if skill_items else None,
        "skill_gap_macro_f1": round(sum(defined_f1) / len(defined_f1), 4) if defined_f1 else None,
        "skill_gap_class_metrics": skill_class_metrics,
        "evidence_claims_checked": evidence_claims,
        "evidence_grounded_claims": grounded_claims,
        "evidence_grounding_rate": round(grounded_claims / evidence_claims, 4) if evidence_claims else None,
        "unsupported_or_unlinked_claims": evidence_claims - grounded_claims,
        "validation_flagged_candidates": flagged_candidates,
        "validation_flag_rate": round(flagged_candidates / evaluated_candidates, 4) if evaluated_candidates else None,
    }

    result = EvaluationResult(
        dataset_id=dataset_id,
        triggered_by_user_id=triggered_by_user_id,
        top_n=top_n,
        metrics=metrics,
        per_query_results=per_query_results,
        notes="Computed from live search-pipeline runs. Ranking uses human relevance labels; skill-gap metrics use recruiter-entered expected skill states; grounding checks returned requirement evidence against persisted source text. Unsupported or unprovided ground truth is reported as null, not scored as a pass.",
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result
