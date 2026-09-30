"""
Structured / metadata filtering (Section 9).

Applied as a *soft* pre-filter that narrows the candidate pool before
lexical+semantic scoring, not a hard SQL WHERE that silently drops
candidates the recruiter might still want to see: a candidate missing a
mandatory requirement is de-prioritized (flagged, scored lower) rather than
invisibly excluded, because Section 15 explicitly warns against
mechanically rejecting close-but-imperfect candidates. Hard exclusion is
reserved for genuinely disqualifying, unambiguous facts (e.g. years of
experience far below the mandatory minimum can down-rank heavily, but the
candidate still appears in the pool with full evidence, so the recruient
can see why they were placed lower).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CandidateMetadata:
    candidate_id: str
    technical_skills: set[str]
    years_of_experience: float | None


def mandatory_skill_coverage(candidate: CandidateMetadata, mandatory_skills: list[str]) -> tuple[int, int]:
    if not mandatory_skills:
        return (0, 0)
    present = sum(1 for s in mandatory_skills if s.lower() in candidate.technical_skills)
    return present, len(mandatory_skills)


def experience_penalty(candidate: CandidateMetadata, min_years: float | None) -> float:
    """Returns a multiplicative penalty in (0, 1]. 1.0 = no penalty."""
    if min_years is None or candidate.years_of_experience is None:
        return 1.0
    if candidate.years_of_experience >= min_years:
        return 1.0
    deficit_ratio = (min_years - candidate.years_of_experience) / max(min_years, 1.0)
    # Soft penalty: even someone with meaningfully less experience is only
    # ever down-weighted, never zeroed out, per Section 15.
    return max(0.4, 1.0 - deficit_ratio)
