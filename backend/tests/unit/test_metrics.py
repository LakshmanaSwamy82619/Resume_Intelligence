from app.evaluation.metrics import (
    evidence_grounding_rate,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    skill_matching_accuracy,
    unsupported_claim_rate,
)


def test_precision_and_recall_at_k():
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c", "z"}
    assert precision_at_k(ranked, relevant, 3) == 2 / 3
    assert recall_at_k(ranked, relevant, 3) == 2 / 3  # z never appears in ranked list


def test_precision_at_k_empty_pool():
    assert precision_at_k([], {"a"}, 3) == 0.0


def test_mrr_finds_first_relevant_rank():
    ranked = ["x", "y", "a", "b"]
    assert mean_reciprocal_rank(ranked, {"a"}) == 1 / 3


def test_mrr_no_relevant_found():
    assert mean_reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_ndcg_perfect_ordering_is_one():
    relevance_map = {"a": 2, "b": 1, "c": 0}
    ranked = ["a", "b", "c"]
    assert abs(ndcg_at_k(ranked, relevance_map, 3) - 1.0) < 1e-9


def test_ndcg_worse_ordering_is_less_than_one():
    relevance_map = {"a": 2, "b": 1, "c": 0}
    ranked = ["c", "b", "a"]
    assert ndcg_at_k(ranked, relevance_map, 3) < 1.0


def test_skill_matching_accuracy_precision_recall_f1():
    predicted_matched = {"python", "sql", "java"}  # java is a false positive
    predicted_missing = {"aws"}
    ground_truth_present = {"python", "sql", "aws"}  # aws was actually present but called missing
    result = skill_matching_accuracy(predicted_matched, predicted_missing, ground_truth_present)
    assert result["precision"] == round(2 / 3, 4)
    assert result["recall"] == round(2 / 3, 4)


def test_evidence_grounding_rate():
    assert evidence_grounding_rate(8, 10) == 0.8
    assert evidence_grounding_rate(0, 0) == 1.0


def test_unsupported_claim_rate():
    assert unsupported_claim_rate(2, 10) == 0.2
    assert unsupported_claim_rate(0, 0) == 0.0
