from app.ranking.config import RankingWeights
from app.ranking.scorer import RankingInputs, compute_final_score, rank_candidates


def _inputs(candidate_id, **overrides):
    base = dict(
        candidate_id=candidate_id,
        reranker_score_normalized=0.5,
        mandatory_matched=2,
        mandatory_total=2,
        preferred_matched=1,
        preferred_total=2,
        skill_alignment_score=0.5,
        experience_relevance_score=0.5,
        project_relevance_score=0.5,
        evidence_confidence_score=1.0,
    )
    base.update(overrides)
    return RankingInputs(**base)


def test_full_mandatory_coverage_scores_higher_than_partial():
    weights = RankingWeights().normalized()
    full = compute_final_score(_inputs("a", mandatory_matched=2, mandatory_total=2), weights)
    partial = compute_final_score(_inputs("b", mandatory_matched=1, mandatory_total=2), weights)
    assert full.final_score > partial.final_score


def test_no_requirements_of_a_type_is_not_penalized():
    weights = RankingWeights().normalized()
    result = compute_final_score(_inputs("a", mandatory_matched=0, mandatory_total=0), weights)
    # mandatory_satisfaction component should be the full weight (ratio defaults to 1.0)
    assert result.breakdown["components"]["mandatory_satisfaction"] == weights.mandatory_satisfaction


def test_project_relevance_breaks_ties_per_section_15_example():
    """Mirrors the spec's Candidate A (exact skills, no ML projects) vs
    Candidate B (slightly less experience, strong ML project evidence)
    example: B should not automatically lose just because of raw
    keyword/experience matching.
    """
    weights = RankingWeights().normalized()
    candidate_a = compute_final_score(
        _inputs("a", experience_relevance_score=1.0, project_relevance_score=0.0, skill_alignment_score=1.0), weights
    )
    candidate_b = compute_final_score(
        _inputs("b", experience_relevance_score=0.85, project_relevance_score=1.0, skill_alignment_score=1.0), weights
    )
    # B's strong project evidence should meaningfully close the gap even
    # though A has marginally better raw experience match.
    assert abs(candidate_a.final_score - candidate_b.final_score) < 0.1


def test_rank_candidates_orders_and_truncates():
    weights = RankingWeights().normalized()
    inputs = [_inputs(str(i), reranker_score_normalized=i / 10) for i in range(10)]
    ranked = rank_candidates(inputs, weights, top_n=3)
    assert len(ranked) == 3
    assert ranked[0].candidate_id == "9"
    assert ranked[0].final_score >= ranked[1].final_score >= ranked[2].final_score


def test_weights_normalize_to_one():
    weights = RankingWeights(mandatory_satisfaction=1, preferred_satisfaction=1, reranker_relevance=1, skill_alignment=1, experience_relevance=1, project_relevance=1, evidence_confidence=1)
    normalized = weights.normalized()
    total = (
        normalized.mandatory_satisfaction
        + normalized.preferred_satisfaction
        + normalized.reranker_relevance
        + normalized.skill_alignment
        + normalized.experience_relevance
        + normalized.project_relevance
        + normalized.evidence_confidence
    )
    assert abs(total - 1.0) < 1e-9
