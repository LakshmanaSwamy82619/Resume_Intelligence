"""
Final ranking configuration (Section 18).

The spec explicitly forbids shipping an arbitrary fixed formula ("70%
semantic / 30% skills") as gospel. What we do instead:

  1. Define every ranking FACTOR as a named, independently-computed,
     evidence-traceable signal (see scorer.py for how each is computed).
  2. Give each factor a documented default weight below, justified in
     comments -- these are reasoned starting points, not measured optimums,
     because (per Section 23) no pre-labelled ground-truth dataset was
     provided with this project. They are NOT presented to the recruiter
     as "accuracy" or "the best candidate" (Section 46) -- only as
     "Top-ranked candidate based on configured matching criteria."
  3. Make the weights a config object that the evaluation module
     (app/evaluation) can grid-search or gradient-tune against a labelled
     EvaluationDataset once one exists, and persist the tuned weights back
     here -- at that point "configurable and measurable" (Section 18)
     becomes literal, not aspirational.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RankingWeights:
    # Whether the candidate covers MANDATORY requirements is the single
    # most consequential factor -- missing a mandatory requirement should
    # visibly hurt rank even if everything else about the resume is strong.
    mandatory_satisfaction: float = 0.30

    # Preferred/nice-to-have coverage matters, but candidates shouldn't be
    # separated primarily on "extra" requirements.
    preferred_satisfaction: float = 0.10

    # Reranker relevance: this already captures deep semantic/contextual
    # fit (Section 14/15) between JD and resume content, so it carries real
    # weight but is not the sole factor (per Section 9's explicit warning).
    reranker_relevance: float = 0.20

    # Skill-gap agent's matched/partial/missing analysis, weighted
    # separately from raw reranker score because it is evidence-grounded
    # and interpretable (recruiter sees exactly which skills).
    skill_alignment: float = 0.15

    # Experience relevance (years + role/title alignment), from the
    # Qualification Agent.
    experience_relevance: float = 0.10

    # Project relevance: does the candidate have hands-on project evidence
    # for the role's core technologies, not just a resume-line mention
    # (Section 15's Candidate A/B example turns on exactly this).
    project_relevance: float = 0.10

    # Evidence confidence / validation: the Explainability/Validation
    # Agent's assessment of how well-supported the recommendation is. Low
    # evidence confidence very mildly discounts rank -- it should surface
    # in the "why selected" explanation and validation_status more than it
    # should silently reorder candidates.
    evidence_confidence: float = 0.05

    def normalized(self) -> "RankingWeights":
        total = (
            self.mandatory_satisfaction
            + self.preferred_satisfaction
            + self.reranker_relevance
            + self.skill_alignment
            + self.experience_relevance
            + self.project_relevance
            + self.evidence_confidence
        )
        if total <= 0:
            return RankingWeights()
        factor = 1.0 / total
        return RankingWeights(
            mandatory_satisfaction=self.mandatory_satisfaction * factor,
            preferred_satisfaction=self.preferred_satisfaction * factor,
            reranker_relevance=self.reranker_relevance * factor,
            skill_alignment=self.skill_alignment * factor,
            experience_relevance=self.experience_relevance * factor,
            project_relevance=self.project_relevance * factor,
            evidence_confidence=self.evidence_confidence * factor,
        )


DEFAULT_RANKING_WEIGHTS = RankingWeights().normalized()
