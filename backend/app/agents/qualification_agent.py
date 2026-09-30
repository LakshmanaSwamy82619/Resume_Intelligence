"""
Qualification Analysis Agent (Section 16.3).

Responsibility: experience (years + role/title relevance), education, and
certifications -- the "is this person qualified for this kind of role"
question, as distinct from the Skill Gap Agent's tools/technologies focus.

Title relevance uses simple lexical overlap between the candidate's past
job titles and the target job title/responsibilities -- deliberately
lightweight (no LLM call) so this agent, too, degrades gracefully with zero
external dependencies; the LLM is reserved for the Explainability Agent's
prose generation where fluency actually matters.
"""
from __future__ import annotations

import re

from app.agents.state import AgentHandoff, AgentState, MatchingAgentResult, QualificationAgentResult, RequirementFinding, SkillGapAgentResult

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def run_qualification_agent(state: AgentState, handoff: AgentHandoff | None = None) -> QualificationAgentResult:
    job = state.job
    candidate = state.candidate
    result = QualificationAgentResult()
    matching_result = None
    if handoff is not None:
        expected_handoff = state.require_handoff("skill_gap", "qualification")
        if handoff is not expected_handoff:
            raise RuntimeError("Qualification Agent was given a handoff that is not addressed to it.")
        handoff = expected_handoff
        matching_result = handoff.payload.get("matching_result")
        skill_gap_result = handoff.payload.get("skill_gap_result")
        if not isinstance(matching_result, MatchingAgentResult) or not isinstance(skill_gap_result, SkillGapAgentResult):
            raise RuntimeError("Qualification Agent received incomplete upstream results.")

    # --- Experience relevance ---
    if job.min_experience_years is None:
        result.experience_relevance_score = 1.0
        result.years_note = "No minimum experience requirement specified."
    elif candidate.years_of_experience is None:
        result.experience_relevance_score = 0.5
        result.years_note = "Years of experience could not be determined from the resume; scored neutrally."
    else:
        ratio = candidate.years_of_experience / job.min_experience_years if job.min_experience_years > 0 else 1.0
        result.experience_relevance_score = round(min(1.0, max(0.3, ratio)), 4)
        if candidate.years_of_experience >= job.min_experience_years:
            result.years_note = f"{candidate.years_of_experience:.1f} years meets the {job.min_experience_years:.1f}-year requirement."
        else:
            result.years_note = f"{candidate.years_of_experience:.1f} years is below the {job.min_experience_years:.1f}-year requirement."

    # --- Title relevance (lexical overlap with job title/responsibilities) ---
    target_text = " ".join([job.title or ""] + job.responsibilities)
    target_tokens = _tokens(target_text)
    if target_tokens and candidate.job_titles:
        best_overlap = 0.0
        best_title = None
        for title in candidate.job_titles:
            title_tokens = _tokens(title)
            if not title_tokens:
                continue
            overlap = len(title_tokens & target_tokens) / len(title_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_title = title
        if best_title and best_overlap > 0:
            result.title_relevance_note = f"Past title '{best_title}' overlaps with the target role's terminology."
            result.experience_relevance_score = round(min(1.0, result.experience_relevance_score * 0.7 + best_overlap * 0.3), 4)
        else:
            result.title_relevance_note = "No strong overlap found between past job titles and the target role."
    else:
        result.title_relevance_note = "Insufficient title information to assess role-title relevance."

    # --- Education ---
    for item in job.mandatory_other + job.preferred_other:
        if item["type"] != "education":
            continue
        prior_finding = next((finding for finding in matching_result.matched + matching_result.missing if finding.requirement.casefold() == item["value"].casefold() and finding.requirement_type == "education"), None) if matching_result else None
        found = prior_finding.status == "matched" if prior_finding else any(item["value"].lower() in str(entry).lower() for entry in candidate.education_entries)
        priority = "mandatory" if item in job.mandatory_other else "preferred"
        result.education_findings.append(
            RequirementFinding(
                requirement=item["value"], requirement_type="education", priority=priority,
                status=prior_finding.status if prior_finding else ("matched" if found else "missing"),
                evidence_text=prior_finding.evidence_text if prior_finding else None,
                page_number=prior_finding.page_number if prior_finding else None,
                source_file=prior_finding.source_file if prior_finding else None,
            )
        )

    # --- Certifications ---
    for item in job.mandatory_other + job.preferred_other:
        if item["type"] != "certification":
            continue
        prior_finding = next((finding for finding in matching_result.matched + matching_result.missing if finding.requirement.casefold() == item["value"].casefold() and finding.requirement_type == "certification"), None) if matching_result else None
        found = prior_finding.status == "matched" if prior_finding else any(item["value"].lower() in str(entry).lower() for entry in candidate.certification_entries)
        priority = "mandatory" if item in job.mandatory_other else "preferred"
        result.certification_findings.append(
            RequirementFinding(
                requirement=item["value"], requirement_type="certification", priority=priority,
                status=prior_finding.status if prior_finding else ("matched" if found else "missing"),
                evidence_text=prior_finding.evidence_text if prior_finding else None,
                page_number=prior_finding.page_number if prior_finding else None,
                source_file=prior_finding.source_file if prior_finding else None,
            )
        )

    return result
