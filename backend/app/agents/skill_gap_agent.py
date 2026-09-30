"""
Skill Gap Analysis Agent (Section 16.2).

Responsibility: specifically skills (not the full requirement set) --
matched / partially matched (adjacent technology present, via
skill_relations clusters) / missing, each with evidence, plus a single
skill_alignment_score in [0,1] used by the final ranking framework.

Distinct from the Candidate Matching Agent: that agent checks ALL
requirement types (skills+education+certs) for pass/fail; this agent goes
deeper specifically on skills and is the one that introduces the
"partial" tier via related-technology detection (Section 15/16).
"""
from __future__ import annotations

from app.agents.skill_relations import find_related_present_skill
from app.agents.state import AgentHandoff, AgentState, MatchingAgentResult, RequirementFinding, SkillGapAgentResult


def _evidence_for(candidate_evidence: list[dict], field_value: str) -> dict | None:
    for ev in candidate_evidence:
        if ev.get("field_value", "").lower() == field_value.lower():
            return ev
    return None


def run_skill_gap_agent(state: AgentState, handoff: AgentHandoff | None = None) -> SkillGapAgentResult:
    job = state.job
    candidate = state.candidate
    candidate_skills = {s.lower() for s in candidate.technical_skills}
    matching_result = None
    if handoff is not None:
        expected_handoff = state.require_handoff("candidate_matching", "skill_gap")
        if handoff is not expected_handoff:
            raise RuntimeError("Skill Gap Agent was given a handoff that is not addressed to it.")
        handoff = expected_handoff
        matching_result = handoff.payload.get("matching_result")
        if not isinstance(matching_result, MatchingAgentResult):
            raise RuntimeError("Skill Gap Agent received an invalid candidate-matching result.")

    result = SkillGapAgentResult()
    all_required = [(s, "mandatory") for s in job.mandatory_skills] + [(s, "preferred") for s in job.preferred_skills]
    exact_matches = {
        finding.requirement.casefold(): finding
        for finding in (matching_result.matched if matching_result else [])
        if finding.requirement_type == "skill"
    }

    for skill, priority in all_required:
        matched_by_previous_agent = exact_matches.get(skill.casefold())
        if matched_by_previous_agent or skill.lower() in candidate_skills:
            ev = _evidence_for(candidate.evidence, skill)
            if matched_by_previous_agent and not ev and matched_by_previous_agent.evidence_text:
                result.matched_skills.append(matched_by_previous_agent)
                continue
            result.matched_skills.append(
                RequirementFinding(
                    requirement=skill, requirement_type="skill", priority=priority, status="matched",
                    evidence_text=ev.get("evidence_text") if ev else None,
                    page_number=ev.get("page_number") if ev else None,
                    source_file=ev.get("source_file") if ev else None,
                )
            )
            continue

        related = find_related_present_skill(skill, candidate_skills)
        if related:
            ev = _evidence_for(candidate.evidence, related)
            result.partial_skills.append(
                RequirementFinding(
                    requirement=skill, requirement_type="skill", priority=priority, status="partial",
                    evidence_text=ev.get("evidence_text") if ev else None,
                    page_number=ev.get("page_number") if ev else None,
                    source_file=ev.get("source_file") if ev else None,
                    note=f"Candidate has '{related}', a related/adjacent technology, but not '{skill}' specifically.",
                )
            )
            continue

        result.missing_skills.append(
            RequirementFinding(requirement=skill, requirement_type="skill", priority=priority, status="missing")
        )

    total = len(all_required)
    if total == 0:
        result.skill_alignment_score = 1.0
    else:
        # Matched skills count fully, partial matches count at half weight,
        # mandatory skills weigh double preferred skills within this score.
        weighted_total = 0.0
        weighted_achieved = 0.0
        for skill, priority in all_required:
            weight = 2.0 if priority == "mandatory" else 1.0
            weighted_total += weight
            if any(f.requirement == skill for f in result.matched_skills):
                weighted_achieved += weight
            elif any(f.requirement == skill for f in result.partial_skills):
                weighted_achieved += weight * 0.5
        result.skill_alignment_score = round(weighted_achieved / weighted_total, 4) if weighted_total else 1.0

    return result
