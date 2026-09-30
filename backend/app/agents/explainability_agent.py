"""
Explainability / Validation Agent (Section 16.4).

Two jobs, in order:

1. VALIDATE: check that every "matched" finding from the Matching and
   Skill Gap agents actually carries a real evidence_text pointer. A
   "matched" finding with no evidence is flagged (validation_status =
   "flagged") rather than silently trusted -- this is the guardrail
   against unsupported claims (Section 16.4/20: "detect unsupported
   claims"). evidence_confidence_score is the fraction of matched/partial
   findings that ARE evidence-backed.

2. EXPLAIN: generate the "Why this candidate" text from validated structured
   facts and cited resume passages. The narrative is deterministic so it
   cannot add claims beyond the evidence displayed to the recruiter.
"""
from __future__ import annotations

import re
from app.agents.state import AgentHandoff, AgentState, ExplainabilityAgentResult, MatchingAgentResult, QualificationAgentResult, SkillGapAgentResult, ValidationFlag
from app.core.config import get_settings
from app.providers.llm.chain import LLMProviderChain
from app.providers.llm.base import LLMResult
from app.providers.llm.deterministic import build_deterministic_explanation

_INSTRUCTION_LIKE_SOURCE = re.compile(
    r"\b(ignore|disregard|override|follow)\b.{0,50}\b(previous|prior|all|these)?\s*(instructions?|prompts?)\b",
    re.IGNORECASE,
)
_NEGATED_EVIDENCE = re.compile(r"\b(?:not|no|never|without|lacks?|doesn't|does\s+not)\b.{0,40}", re.IGNORECASE)


def _contradicts(text: str | None, requirement: str) -> bool:
    if not text:
        return False
    target = re.escape(requirement.casefold())
    return any(
        re.search(r"(?<![a-z0-9])" + target + r"(?![a-z0-9])", phrase.casefold())
        for phrase in _NEGATED_EVIDENCE.findall(text)
    )


def _is_supported_finding(finding) -> bool:
    return bool(finding.evidence_text) and not _contradicts(finding.evidence_text, finding.requirement)


def _validate(state: AgentState) -> tuple[str, list[ValidationFlag], float]:
    matching = state.matching_result
    skill_gap = state.skill_gap_result
    assert matching is not None and skill_gap is not None

    checkable = matching.matched + skill_gap.matched_skills + skill_gap.partial_skills
    flags: list[ValidationFlag] = []
    evidence_backed = 0

    for finding in checkable:
        if _is_supported_finding(finding):
            evidence_backed += 1
        else:
            issue = (
                "Source evidence appears to contradict this claim; treat it as unsupported."
                if _contradicts(finding.evidence_text, finding.requirement)
                else "No resume evidence sentence found for this claim; treat with caution."
            )
            flags.append(
                ValidationFlag(
                    claim=f"{finding.requirement} ({finding.status})",
                    issue=issue,
                )
            )

    # No matched/partial claims means there is no evidence to credit. Treating
    # an empty set as fully supported incorrectly awards the ranking evidence
    # bonus to candidates whose resume yielded no checkable evidence.
    confidence = (evidence_backed / len(checkable)) if checkable else 0.0
    status = "validated" if not flags else "flagged"
    return status, flags, round(confidence, 4)


def _collect_top_evidence(state: AgentState, limit: int = 5) -> list[dict]:
    matching = state.matching_result
    skill_gap = state.skill_gap_result
    assert matching is not None and skill_gap is not None

    findings = [
        f for f in matching.matched + skill_gap.matched_skills + skill_gap.partial_skills
        if _is_supported_finding(f)
    ]
    has_experience_evidence = any(
        ev.get("field_type") == "experience" and ev.get("evidence_text")
        for ev in state.candidate.evidence
    )
    finding_limit = limit - 1 if has_experience_evidence and limit > 0 else limit
    seen_texts = set()
    evidence = []

    def resume_id_for(evidence_text: str | None, source_file: str | None, page_number: int | None):
        normalized_text = " ".join((evidence_text or "").casefold().split())
        for source in state.candidate.evidence:
            same_text = " ".join(str(source.get("evidence_text") or "").casefold().split()) == normalized_text
            same_file = not source_file or not source.get("source_file") or source.get("source_file") == source_file
            same_page = page_number is None or source.get("page_number") is None or source.get("page_number") == page_number
            if normalized_text and same_text and same_file and same_page:
                return source.get("resume_id")
        return None

    for f in findings:
        if f.evidence_text in seen_texts:
            continue
        seen_texts.add(f.evidence_text)
        evidence.append(
            {
                "requirement": f.requirement,
                "evidence_text": f.evidence_text,
                "source_file": f.source_file,
                "page_number": f.page_number,
                "resume_id": resume_id_for(f.evidence_text, f.source_file, f.page_number),
            }
        )
        if len(evidence) >= finding_limit:
            break
    # Experience totals are only suitable for explanation when there is a
    # corresponding source passage to cite. Keep the passage in the same
    # provenance-bearing evidence list used by the API.
    for ev in state.candidate.evidence:
        if ev.get("field_type") != "experience" or not ev.get("evidence_text"):
            continue
        if ev["evidence_text"] in seen_texts:
            continue
        evidence.append(
            {
                "requirement": "experience",
                "evidence_text": ev["evidence_text"],
                "source_file": ev.get("source_file"),
                "page_number": ev.get("page_number"),
                "resume_id": ev.get("resume_id"),
            }
        )
        seen_texts.add(ev["evidence_text"])
        if len(evidence) >= limit:
            break
    return evidence


async def run_explainability_agent(state: AgentState, llm_chain: LLMProviderChain | None, handoff: AgentHandoff | None = None) -> ExplainabilityAgentResult:
    if handoff is not None:
        expected_handoff = state.require_handoff("qualification", "explainability")
        if handoff is not expected_handoff:
            raise RuntimeError("Explainability Agent was given a handoff that is not addressed to it.")
        handoff = expected_handoff
        matching = handoff.payload.get("matching_result")
        skill_gap = handoff.payload.get("skill_gap_result")
        qualification = handoff.payload.get("qualification_result")
        if not isinstance(matching, MatchingAgentResult) or not isinstance(skill_gap, SkillGapAgentResult) or not isinstance(qualification, QualificationAgentResult):
            raise RuntimeError("Explainability Agent received incomplete upstream results.")
        state.matching_result, state.skill_gap_result, state.qualification_result = matching, skill_gap, qualification
    matching = state.matching_result
    skill_gap = state.skill_gap_result
    qualification = state.qualification_result
    assert matching is not None and skill_gap is not None and qualification is not None

    status, flags, confidence = _validate(state)
    top_evidence = _collect_top_evidence(state)
    all_matched = matching.matched + skill_gap.matched_skills
    supported_matched = [f for f in all_matched if _is_supported_finding(f)]
    unsupported_matched = [f for f in all_matched if not _is_supported_finding(f)]
    supported_partial = [f for f in skill_gap.partial_skills if _is_supported_finding(f)]
    unsupported_partial = [f for f in skill_gap.partial_skills if not _is_supported_finding(f)]
    experience_is_cited = any(ev.get("requirement") == "experience" for ev in top_evidence)
    experience_is_evidenced = any(
        ev.get("field_type") == "experience" and ev.get("evidence_text")
        for ev in state.candidate.evidence
    )
    explained_years = state.candidate.years_of_experience if experience_is_evidenced and experience_is_cited else None

    result = ExplainabilityAgentResult(
        validation_status=status,
        validation_notes=flags,
        evidence_confidence_score=confidence,
    )

    deterministic_kwargs = dict(
        candidate_name=state.candidate.full_name or "This candidate",
        matched=[{"requirement": f.requirement} for f in supported_matched],
        partial=[{"requirement": f.requirement} for f in supported_partial],
        missing=[{"requirement": f.requirement} for f in (matching.missing + skill_gap.missing_skills + unsupported_matched + unsupported_partial)],
        years_of_experience=explained_years,
        top_evidence=[
            {
                "evidence_text": e["evidence_text"],
                "source_file": e["source_file"] or "resume",
                "page_number": e["page_number"] if e["page_number"] is not None else "n/a",
            }
            for e in top_evidence
        ],
    )

    untrusted_instruction_in_source = any(
        _INSTRUCTION_LIKE_SOURCE.search(item.get("evidence_text", "")) for item in state.candidate.evidence
    )
    settings = get_settings()
    llm_result = None
    has_configured_key = bool(settings.LLM_API_KEY.strip())
    is_injected_provider = llm_chain is not None and not hasattr(llm_chain, "providers")
    if llm_chain is not None and (has_configured_key or is_injected_provider) and not untrusted_instruction_in_source:
        deterministic_result = build_deterministic_explanation(**deterministic_kwargs)
        approved_facts = [line for line in deterministic_result.text.splitlines() if line.strip()]
        system_prompt = (
            "Review the job requirements and validated candidate facts. In a short plain-text "
            "response, identify which supplied facts are most relevant to the job. Do not infer "
            "or add candidate qualifications. The application will display only its original "
            "validated facts, not your wording."
        )
        requirements = [
            *state.job.mandatory_skills,
            *state.job.preferred_skills,
            *(str(item.get("value", "")) for item in state.job.mandatory_other),
            *(str(item.get("value", "")) for item in state.job.preferred_other),
        ]
        user_prompt = (
            f"Role: {state.job.title or 'Not specified'}\n"
            f"Hiring requirements: {', '.join(value for value in requirements if value) or 'Not specified'}\n"
            "Validated candidate facts:\n" + "\n".join(approved_facts)
        )
        try:
            response = await llm_chain.complete(system_prompt, user_prompt, temperature=0.0, max_tokens=500)
            if not response.fallback_used and response.text.strip():
                response_tokens = set(re.findall(r"[a-z0-9+#.-]+", response.text.casefold()))
                trusted_text = (user_prompt + " " + " ".join(approved_facts)).casefold()
                trusted_tokens = set(re.findall(r"[a-z0-9+#.-]+", trusted_text))
                unfamiliar_names = {
                    term for term in re.findall(r"\b[A-Z][A-Za-z0-9+#.-]{2,}\b", response.text)
                    if term.casefold() not in trusted_text
                }
                overlap = len(response_tokens & trusted_tokens) / max(1, len(response_tokens))
                if unfamiliar_names or overlap < 0.2:
                    result.validation_status = "flagged"
                    issue = (
                        f"The LLM response included unverified term(s): {', '.join(sorted(unfamiliar_names))}. "
                        "They were excluded; displayed facts remain resume-grounded."
                        if unfamiliar_names else
                        "The LLM response could not be grounded to the supplied facts. It was excluded; displayed facts remain resume-grounded."
                    )
                    result.validation_notes.append(ValidationFlag(claim="LLM response", issue=issue))
                ranked_facts = sorted(
                    enumerate(approved_facts),
                    key=lambda pair: (
                        -len(set(re.findall(r"[a-z0-9+#.-]+", pair[1].casefold())) & response_tokens),
                        pair[0],
                    ),
                )
                llm_result = LLMResult(
                    text="\n".join(fact for _, fact in ranked_facts),
                    provider=response.provider,
                    model_used=response.model_used,
                    fallback_used=False,
                    latency_ms=response.latency_ms,
                )
            else:
                fallback_detail = response.fallback_reason or "The provider returned no usable response."
        except Exception as exc:
            fallback_detail = f"LLM explanation step failed: {exc}"
            if not isinstance(exc, (TimeoutError, ConnectionError)):
                result.validation_status = "flagged"
                result.validation_notes.append(
                    ValidationFlag(
                        claim="LLM response",
                        issue="The model response could not be validated; deterministic resume facts were retained.",
                    )
                )
    else:
        if untrusted_instruction_in_source:
            fallback_detail = "Resume text contained instruction-like content; external explanation was skipped."
        elif llm_chain is None or settings.LLM_PROVIDER == "none":
            fallback_detail = "No LLM provider was configured; using validated resume facts."
        elif not settings.LLM_API_KEY.strip():
            fallback_detail = "LLM_API_KEY is not configured; using validated resume facts."
        else:
            fallback_detail = "LLM explanation was unavailable; using validated resume facts."

    if llm_result is None:
        llm_result = build_deterministic_explanation(
            **deterministic_kwargs,
            fallback_reason=fallback_detail,
        )
    if untrusted_instruction_in_source:
        result.validation_status = "flagged"
        result.validation_notes.append(
            ValidationFlag(
                claim="Resume evidence",
                issue="Instruction-like content was present; explanation was generated locally from validated facts only.",
            )
        )

    result.ai_provider = llm_result.provider
    result.fallback_used = llm_result.fallback_used
    result.fallback_reason = llm_result.fallback_reason
    result.top_evidence = top_evidence

    result.explanation_summary = llm_result.text
    result.explanation_points = [line for line in llm_result.text.split("\n") if line.strip()]

    return result
