from __future__ import annotations

from dataclasses import dataclass, field

from app.ranking.config import RankingWeights


@dataclass
class RankingInputs:
    candidate_id: str
    reranker_score_normalized: float  # 0..1
    mandatory_matched: int
    mandatory_total: int
    preferred_matched: int
    preferred_total: int
    skill_alignment_score: float  # 0..1, from Skill Gap Agent
    experience_relevance_score: float  # 0..1, from Qualification Agent
    project_relevance_score: float  # 0..1, from Candidate Matching Agent
    evidence_confidence_score: float  # 0..1, from Explainability/Validation Agent


@dataclass
class RankedCandidate:
    candidate_id: str
    final_score: float
    breakdown: dict = field(default_factory=dict)


def _coverage_ratio(matched: int, total: int) -> float:
    if total == 0:
        return 1.0  # no requirements of this kind -> nothing to be penalized for
    return matched / total


def compute_final_score(inputs: RankingInputs, weights: RankingWeights) -> RankedCandidate:
    mandatory_ratio = _coverage_ratio(inputs.mandatory_matched, inputs.mandatory_total)
    preferred_ratio = _coverage_ratio(inputs.preferred_matched, inputs.preferred_total)

    components = {
        "mandatory_satisfaction": mandatory_ratio * weights.mandatory_satisfaction,
        "preferred_satisfaction": preferred_ratio * weights.preferred_satisfaction,
        "reranker_relevance": inputs.reranker_score_normalized * weights.reranker_relevance,
        "skill_alignment": inputs.skill_alignment_score * weights.skill_alignment,
        "experience_relevance": inputs.experience_relevance_score * weights.experience_relevance,
        "project_relevance": inputs.project_relevance_score * weights.project_relevance,
        "evidence_confidence": inputs.evidence_confidence_score * weights.evidence_confidence,
    }
    final_score = sum(components.values())

    return RankedCandidate(
        candidate_id=inputs.candidate_id,
        final_score=round(final_score, 6),
        breakdown={
            "components": components,
            "mandatory_coverage": f"{inputs.mandatory_matched}/{inputs.mandatory_total}",
            "preferred_coverage": f"{inputs.preferred_matched}/{inputs.preferred_total}",
            "weights_used": weights.__dict__,
        },
    )


def rank_candidates(inputs_list: list[RankingInputs], weights: RankingWeights, top_n: int) -> list[RankedCandidate]:
    scored = [compute_final_score(inp, weights) for inp in inputs_list]
    scored.sort(key=lambda r: r.final_score, reverse=True)
    return scored[:top_n]
