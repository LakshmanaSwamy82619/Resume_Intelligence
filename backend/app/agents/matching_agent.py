"""
Candidate Matching Agent (Section 16.1).

Responsibility: compare the candidate against ALL job requirements
(skills, education, certifications) as a first pass, and separately assess
project relevance -- does the candidate have hands-on project evidence
touching the role's core technologies, not just a resume-line mention.
This is the agent whose output most directly prevents the Section 15
"Candidate A vs B" failure mode: raw skill-keyword presence alone is not
enough, so project evidence is scored as its own signal.

Deterministic by design: this agent does NOT call an LLM. Its comparisons
are exact-match / evidence-presence checks, which is the appropriate tool
for "is this concrete requirement satisfied" -- the fuzzier "does this
overall profile fit the role" judgement is left to reranking + the final
ranking framework, and prose explanation is the Explainability Agent's job.
Keeping this agent deterministic also means the whole matching stage keeps
working even if every LLM provider is down (Section 12/13).
"""
from __future__ import annotations

from app.agents.state import AgentState, MatchingAgentResult, RequirementFinding


def _evidence_for(candidate_evidence: list[dict], field_value: str) -> dict | None:
    for ev in candidate_evidence:
        if ev.get("field_value", "").lower() == field_value.lower():
            return ev
    return None


def run_candidate_matching_agent(state: AgentState) -> MatchingAgentResult:
    job = state.job
    candidate = state.candidate
    candidate_skills = {s.lower() for s in candidate.technical_skills}

    result = MatchingAgentResult()

    def _check(requirement_value: str, requirement_type: str, priority: str):
        if requirement_type == "skill":
            if requirement_value.lower() in candidate_skills:
                ev = _evidence_for(candidate.evidence, requirement_value)
                result.matched.append(
                    RequirementFinding(
                        requirement=requirement_value, requirement_type=requirement_type, priority=priority,
                        status="matched", evidence_text=ev.get("evidence_text") if ev else None,
                        page_number=ev.get("page_number") if ev else None,
                        source_file=ev.get("source_file") if ev else None,
                    )
                )
            else:
                result.missing.append(
                    RequirementFinding(requirement=requirement_value, requirement_type=requirement_type, priority=priority, status="missing")
                )
        else:
            # education/certification: check structured entries + evidence text
            haystacks = candidate.education_entries + candidate.certification_entries
            found = any(requirement_value.lower() in str(entry).lower() for entry in haystacks)
            if found:
                ev = _evidence_for(candidate.evidence, requirement_value)
                result.matched.append(
                    RequirementFinding(
                        requirement=requirement_value, requirement_type=requirement_type, priority=priority,
                        status="matched", evidence_text=ev.get("evidence_text") if ev else None,
                        page_number=ev.get("page_number") if ev else None,
                        source_file=ev.get("source_file") if ev else None,
                    )
                )
            else:
                result.missing.append(
                    RequirementFinding(requirement=requirement_value, requirement_type=requirement_type, priority=priority, status="missing")
                )

    for skill in job.mandatory_skills:
        _check(skill, "skill", "mandatory")
    for skill in job.preferred_skills:
        _check(skill, "skill", "preferred")
    for item in job.mandatory_other:
        _check(item["value"], item["type"], "mandatory")
    for item in job.preferred_other:
        _check(item["value"], item["type"], "preferred")

    # Project relevance: fraction of (mandatory ∪ preferred) skills that
    # show up specifically inside a PROJECT's technology list or
    # description, not merely the flat skills section.
    all_required = {s.lower() for s in job.mandatory_skills + job.preferred_skills}
    if all_required and candidate.project_entries:
        project_tech_hits: set[str] = set()
        for proj in candidate.project_entries:
            tech_list = {t.lower() for t in proj.get("technologies", [])}
            desc = proj.get("description", "").lower()
            for req in all_required:
                if req in tech_list or req in desc:
                    project_tech_hits.add(req)
        result.project_relevance_score = round(len(project_tech_hits) / len(all_required), 4)
    else:
        result.project_relevance_score = 0.0

    matched_count = len(result.matched)
    total_count = matched_count + len(result.missing)
    result.overall_alignment_note = (
        f"{matched_count}/{total_count} explicit requirements satisfied; "
        f"project evidence covers {result.project_relevance_score * 100:.0f}% of required skills."
    )

    return result
