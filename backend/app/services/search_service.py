"""
The core search pipeline (Sections 9/14/16/17/18/19/20), wired end to end:

    Job Requirement
      -> Hybrid Retrieval (candidate pool)
      -> Reranking (narrow to top-K)
      -> Four-Agent deep analysis per candidate
      -> Final Ranking (configurable framework)
      -> Top-N persisted as a Search + SearchCandidate rows

Every external-AI dependency (embeddings, reranker, LLM) goes through its
provider chain, so a full run always completes -- with `fallback_used` /
`ai_provider` / `processing_mode` recorded on the Search row either way
(Section 33).
"""
from __future__ import annotations

from dataclasses import replace
import time
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import run_agent_pipeline
from app.agents.state import AgentState, CandidateInput, JobRequirementInput
from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.models.candidate import Candidate, Resume, ResumeEvidence
from app.models.enums import RetrievalMethod
from app.models.job import JobDescription
from app.models.search import Search, SearchCandidate
from app.providers.embeddings.chain import get_embedding_provider_chain
from app.providers.llm.chain import LLMProviderChain
from app.providers.reranker.chain import get_reranker_provider_chain
from app.ranking.config import DEFAULT_RANKING_WEIGHTS
from app.ranking.scorer import RankingInputs, rank_candidates
from app.retrieval.filters import CandidateMetadata
from app.retrieval.hybrid import hybrid_retrieve

settings = get_settings()


async def _load_all_candidates(db: AsyncSession) -> list[Candidate]:
    stmt = select(Candidate).options(
        selectinload(Candidate.experience),
        selectinload(Candidate.projects),
        selectinload(Candidate.education),
        selectinload(Candidate.certifications),
        selectinload(Candidate.resumes),
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def _load_evidence_for_candidates(db: AsyncSession, candidate_ids: list[str]) -> dict[str, list[dict]]:
    if not candidate_ids:
        return {}
    stmt = (
        select(ResumeEvidence, Resume.original_filename, Resume.id)
        .join(Resume, Resume.id == ResumeEvidence.resume_id)
        .where(ResumeEvidence.candidate_id.in_(candidate_ids))
    )
    result = await db.execute(stmt)
    by_candidate: dict[str, list[dict]] = {cid: [] for cid in candidate_ids}
    for ev, source_file, resume_id in result.all():
        by_candidate.setdefault(ev.candidate_id, []).append(
            {
                "field_type": ev.field_type,
                "field_value": ev.field_value,
                "evidence_text": ev.evidence_text,
                "page_number": ev.page_number,
                "source_file": source_file,
                "resume_id": resume_id,
            }
        )
    return by_candidate


def _candidate_full_text(candidate: Candidate) -> str:
    parts = [candidate.summary or ""]
    parts += candidate.job_titles or []
    parts += [f"{e.title or ''} {e.company or ''} {e.responsibilities_text or ''}" for e in candidate.experience]
    parts += [f"{p.name or ''} {p.description or ''}" for p in candidate.projects]
    parts += candidate.technical_skills + candidate.soft_skills
    parts += [f"{e.degree or ''} {e.institution or ''}" for e in candidate.education]
    parts += [c.name or "" for c in candidate.certifications]
    return "\n".join(p for p in parts if p)


def _as_unverified_missing(finding):
    return replace(
        finding,
        status="missing",
        evidence_text=None,
        page_number=None,
        source_file=None,
        note="This possible match did not pass resume evidence validation.",
    )


async def run_search(
    db: AsyncSession,
    hr_user_id: str,
    query_text: str,
    job: JobDescription | None,
    top_n: int,
    llm_chain: LLMProviderChain | None = None,
    candidate_filters: dict | None = None,
) -> Search:
    start_time = time.perf_counter()
    llm_chain = llm_chain if llm_chain is not None else LLMProviderChain()
    embedding_chain = get_embedding_provider_chain()
    reranker_chain = get_reranker_provider_chain()

    if not query_text.strip() and job is None:
        raise ValidationAppError("A job description or a natural-language hiring requirement is required.")

    requirements_started = time.perf_counter()
    user_query = query_text.strip()
    if job:
        query_parts = []
        if job.title:
            query_parts.append(f"Role: {job.title}")
        query_parts.append(job.raw_text)
        if job.requirements:
            requirement_lines = [
                f"{r.priority.title()} {r.requirement_type}: {r.value}"
                for r in job.requirements
            ]
            query_parts.append("Current recruiter-edited requirements:\n" + "\n".join(requirement_lines))
        if user_query:
            query_parts.append(f"Additional hiring requirements:\n{user_query}")
        effective_query = "\n\n".join(query_parts)
    else:
        effective_query = user_query

    mandatory_skills = [r.value for r in job.requirements if r.priority == "mandatory" and r.requirement_type == "skill"] if job else []
    preferred_skills = [r.value for r in job.requirements if r.priority == "preferred" and r.requirement_type == "skill"] if job else []
    mandatory_other = [
        {"type": r.requirement_type, "value": r.value} for r in job.requirements if r.priority == "mandatory" and r.requirement_type != "skill"
    ] if job else []
    preferred_other = [
        {"type": r.requirement_type, "value": r.value} for r in job.requirements if r.priority == "preferred" and r.requirement_type != "skill"
    ] if job else []
    min_years = job.min_experience_years if job else None
    responsibilities = job.extracted_responsibilities if job else []
    job_title = job.title if job else None

    # If no JD was provided at all, fall back to treating the raw query as a
    # short natural-language requirement for extraction purposes.
    if job is None:
        from app.ingestion.jd_extraction import extract_requirements_rule_based

        parsed = extract_requirements_rule_based(effective_query, is_short_query=True)
        mandatory_skills = [r.value for r in parsed.mandatory() if r.requirement_type == "skill"]
        preferred_skills = [r.value for r in parsed.preferred() if r.requirement_type == "skill"]
        mandatory_other = [
            {"type": r.requirement_type, "value": r.value}
            for r in parsed.mandatory()
            if r.requirement_type != "skill"
        ]
        preferred_other = [
            {"type": r.requirement_type, "value": r.value}
            for r in parsed.preferred()
            if r.requirement_type != "skill"
        ]
        min_years = parsed.min_experience_years
        responsibilities = parsed.responsibilities
        job_title = parsed.title
        has_requirement_signal = bool(parsed.requirements or min_years is not None)
    else:
        has_requirement_signal = True
    requirements_ms = round((time.perf_counter() - requirements_started) * 1000, 2)

    corpus_started = time.perf_counter()
    candidates = await _load_all_candidates(db)
    resumes_considered = len(candidates)
    if resumes_considered == 0:
        raise ValidationAppError("No processed candidates are available to search yet.")

    if not has_requirement_signal:
        query_terms = set(re.findall(r"[a-z0-9+#.]+", effective_query.casefold())) - {
            "a", "an", "the", "and", "or", "for", "with", "in", "to", "of", "find", "candidate", "candidates", "who", "have", "has", "need", "looking"
        }
        title_match = any(
            query_terms.intersection(
                term
                for title in (candidate.job_titles or [])
                for term in re.findall(r"[a-z0-9+#.]+", str(title).casefold())
            )
            for candidate in candidates
        )
        if not title_match:
            raise ValidationAppError(
                "We couldn't identify a role or hiring requirement in that query. Add a role title, skill, education, certification, or experience requirement and try again."
            )

    candidate_filters = candidate_filters or {}
    filter_skills = [str(value).strip().casefold() for value in candidate_filters.get("skills", []) if str(value).strip()]
    filter_education = [str(value).strip().casefold() for value in candidate_filters.get("education", []) if str(value).strip()]
    filter_certifications = [str(value).strip().casefold() for value in candidate_filters.get("certifications", []) if str(value).strip()]
    min_filter_years = candidate_filters.get("min_experience_years")
    max_filter_years = candidate_filters.get("max_experience_years")

    def matches_candidate_filters(candidate: Candidate) -> bool:
        years = candidate.years_of_experience
        if min_filter_years is not None and (years is None or years < min_filter_years):
            return False
        if max_filter_years is not None and (years is None or years > max_filter_years):
            return False
        candidate_skills = [value.casefold() for value in (candidate.technical_skills or []) + (candidate.soft_skills or [])]
        resume_text = "\n".join((resume.raw_text or "").casefold() for resume in candidate.resumes)
        if filter_skills and not any(
            any(term in skill for skill in candidate_skills) or term in resume_text
            for term in filter_skills
        ):
            return False
        education_text = [" ".join(str(value or "") for value in (item.degree, item.field_of_study, item.institution)).casefold() for item in candidate.education]
        if filter_education and not any(
            any(term in text for text in education_text) or term in resume_text
            for term in filter_education
        ):
            return False
        certification_text = [str(item.name or "").casefold() for item in candidate.certifications]
        if filter_certifications and not any(
            any(term in text for text in certification_text) or term in resume_text
            for term in filter_certifications
        ):
            return False
        return True

    candidates = [candidate for candidate in candidates if matches_candidate_filters(candidate)]
    if not candidates:
        raise ValidationAppError("No candidates match the selected filters together. Try a lower minimum experience, a higher maximum, or different values in one of the filter categories.")
    applied_filters = {
        "min_experience_years": min_filter_years,
        "max_experience_years": max_filter_years,
        "skills": filter_skills,
        "education": filter_education,
        "certifications": filter_certifications,
        "candidates_after_filters": len(candidates),
        "candidates_before_filters": resumes_considered,
    }

    candidate_texts = {c.id: _candidate_full_text(c) for c in candidates}
    candidate_metadata = {
        c.id: CandidateMetadata(candidate_id=c.id, technical_skills=set(s.lower() for s in c.technical_skills), years_of_experience=c.years_of_experience)
        for c in candidates
    }
    corpus_ms = round((time.perf_counter() - corpus_started) * 1000, 2)

    retrieval_started = time.perf_counter()
    hybrid_hits, retrieval_meta = await hybrid_retrieve(
        db=db,
        embedding_chain=embedding_chain,
        query_text=effective_query,
        candidate_texts=candidate_texts,
        candidate_metadata=candidate_metadata,
        mandatory_skills=mandatory_skills,
        min_years=min_years,
    )
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
    candidate_pool_size = len(hybrid_hits)

    # --- Reranking stage ---
    rerank_pool = hybrid_hits[: settings.RETRIEVAL_CANDIDATE_POOL_SIZE]
    candidates_by_id = {c.id: c for c in candidates}
    documents_to_rerank = [candidate_texts[h.candidate_id][:2000] for h in rerank_pool]
    rerank_started = time.perf_counter()
    rerank_scores = await reranker_chain.rerank(effective_query, documents_to_rerank)
    rerank_ms = round((time.perf_counter() - rerank_started) * 1000, 2)
    retrieval_meta["providers"] = {
        "embedding": {
            "provider": embedding_chain.last_provider_used,
            "fallback_used": embedding_chain.last_fallback_used,
            "fallback_reason": embedding_chain.last_fallback_reason,
        },
        "reranker": {
            "provider": reranker_chain.last_provider_used,
            "fallback_used": reranker_chain.last_fallback_used,
            "fallback_reason": reranker_chain.last_fallback_reason,
        },
        "llm": {"providers": [], "fallback_used": False, "fallback_reasons": []},
    }

    reranked = sorted(zip(rerank_pool, rerank_scores), key=lambda pair: pair[1], reverse=True)
    top_for_deep_analysis = reranked[: settings.RETRIEVAL_RERANK_TOP_K]

    if top_for_deep_analysis:
        raw_scores = [s for _, s in top_for_deep_analysis]
        lo, hi = min(raw_scores), max(raw_scores)
        span = (hi - lo) or 1.0
        normalized_rerank = {hit.candidate_id: (score - lo) / span for hit, score in top_for_deep_analysis}
    else:
        normalized_rerank = {}

    # --- Deep per-candidate agent analysis ---
    evidence_started = time.perf_counter()
    evidence_by_candidate = await _load_evidence_for_candidates(db, [h.candidate_id for h, _ in top_for_deep_analysis])
    evidence_ms = round((time.perf_counter() - evidence_started) * 1000, 2)

    job_input = JobRequirementInput(
        title=job_title,
        mandatory_skills=mandatory_skills,
        preferred_skills=preferred_skills,
        mandatory_other=mandatory_other,
        preferred_other=preferred_other,
        min_experience_years=min_years,
        responsibilities=responsibilities,
    )

    ranking_inputs: list[RankingInputs] = []
    agent_states: dict[str, AgentState] = {}
    any_fallback_used = embedding_chain.last_fallback_used or reranker_chain.last_fallback_used
    fallback_reasons: list[str] = []
    ai_providers_used: set[str] = set()
    llm_fallback_reasons: set[str] = set()
    if embedding_chain.last_fallback_reason:
        fallback_reasons.append(f"embedding: {embedding_chain.last_fallback_reason}")
    if reranker_chain.last_fallback_reason:
        fallback_reasons.append(f"reranker: {reranker_chain.last_fallback_reason}")

    analysis_started = time.perf_counter()
    for hit, _raw_score in top_for_deep_analysis:
        candidate = candidates_by_id[hit.candidate_id]
        candidate_input = CandidateInput(
            candidate_id=candidate.id,
            full_name=candidate.full_name,
            technical_skills=candidate.technical_skills,
            job_titles=candidate.job_titles,
            years_of_experience=candidate.years_of_experience,
            experience_entries=[
                {"company": e.company, "title": e.title, "duration_years": e.duration_years} for e in candidate.experience
            ],
            project_entries=[
                {"name": p.name, "description": p.description or "", "technologies": p.technologies} for p in candidate.projects
            ],
            education_entries=[
                {"degree": e.degree, "institution": e.institution} for e in candidate.education
            ],
            certification_entries=[{"name": c.name} for c in candidate.certifications],
            evidence=evidence_by_candidate.get(candidate.id, []),
        )
        state = AgentState(job=job_input, candidate=candidate_input, reranker_score_normalized=normalized_rerank.get(candidate.id, 0.0))
        state = await run_agent_pipeline(state, llm_chain)
        agent_states[candidate.id] = state

        if state.explainability_result.fallback_used:
            any_fallback_used = True
            if state.explainability_result.fallback_reason:
                fallback_reasons.append(state.explainability_result.fallback_reason)
                llm_fallback_reasons.add(state.explainability_result.fallback_reason)
        ai_providers_used.add(state.explainability_result.ai_provider)

        m, sg, q, ex = state.matching_result, state.skill_gap_result, state.qualification_result, state.explainability_result

        def _dedupe_keys(findings):
            seen = set()
            deduped = []
            for f in findings:
                key = (f.requirement.lower(), f.requirement_type)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(f)
            return deduped

        unsupported_claims = {flag.claim for flag in ex.validation_notes}

        def has_validated_evidence(finding):
            return bool(finding.evidence_text) and f"{finding.requirement} ({finding.status})" not in unsupported_claims

        raw_matched = m.matched + sg.matched_skills
        raw_partial = sg.partial_skills
        unsupported_findings = [_as_unverified_missing(finding) for finding in raw_matched + raw_partial if not has_validated_evidence(finding)]
        matched_dedup = _dedupe_keys([finding for finding in raw_matched if has_validated_evidence(finding)])
        partial_dedup = _dedupe_keys([finding for finding in raw_partial if has_validated_evidence(finding)])
        missing_dedup = _dedupe_keys(m.missing + sg.missing_skills + unsupported_findings)

        mandatory_matched = sum(1 for f in matched_dedup if f.priority == "mandatory")
        mandatory_total = sum(1 for f in (matched_dedup + missing_dedup + partial_dedup) if f.priority == "mandatory")
        preferred_matched = sum(1 for f in matched_dedup if f.priority == "preferred")
        preferred_total = sum(1 for f in (matched_dedup + missing_dedup + partial_dedup) if f.priority == "preferred")

        ranking_inputs.append(
            RankingInputs(
                candidate_id=candidate.id,
                reranker_score_normalized=normalized_rerank.get(candidate.id, 0.0),
                mandatory_matched=mandatory_matched,
                mandatory_total=mandatory_total,
                preferred_matched=preferred_matched,
                preferred_total=preferred_total,
                skill_alignment_score=sg.skill_alignment_score,
                experience_relevance_score=q.experience_relevance_score,
                project_relevance_score=m.project_relevance_score,
                evidence_confidence_score=ex.evidence_confidence_score,
            )
        )

    analysis_ms = round((time.perf_counter() - analysis_started) * 1000, 2)
    ranking_started = time.perf_counter()
    ranked = rank_candidates(ranking_inputs, DEFAULT_RANKING_WEIGHTS, top_n)
    ranking_ms = round((time.perf_counter() - ranking_started) * 1000, 2)

    processing_time_ms = (time.perf_counter() - start_time) * 1000
    handoff_routes: dict[tuple[str, str], dict[str, object]] = {}
    for state in agent_states.values():
        for handoff in state.handoff_trace():
            route = (handoff["from"], handoff["to"])
            entry = handoff_routes.setdefault(route, {"from": route[0], "to": route[1], "transfer_count": 0, "artifacts": handoff["artifacts"]})
            entry["transfer_count"] = int(entry["transfer_count"]) + 1
    processing_mode = "full_ai" if not any_fallback_used else ("partial_fallback" if ai_providers_used - {"deterministic"} else "deterministic")
    retrieval_meta["providers"]["llm"] = {
        "providers": sorted(ai_providers_used),
        "fallback_used": bool(llm_fallback_reasons),
        "fallback_reasons": sorted(llm_fallback_reasons),
    }
    retrieval_meta["pipeline"] = {
        "stages": [
            {
                "id": "requirements",
                "label": "Understand hiring requirements",
                "duration_ms": requirements_ms,
                "details": {
                    "input_mode": "saved_job_brief" if job else "natural_language",
                    "mandatory_requirements": len(mandatory_skills) + len(mandatory_other),
                    "preferred_requirements": len(preferred_skills) + len(preferred_other),
                    "minimum_experience_years": min_years,
                    "candidate_filters": applied_filters,
                },
            },
            {
                "id": "candidate_corpus",
                "label": "Load indexed candidate profiles",
                "duration_ms": corpus_ms,
                    "details": {"candidates_loaded": resumes_considered, "candidates_after_filters": len(candidates), "candidate_filters": applied_filters},
            },
            {
                "id": "hybrid_retrieval",
                "label": "Retrieve relevant profiles and resume chunks",
                "duration_ms": retrieval_ms,
                "details": {
                    "retrieval_method": RetrievalMethod.HYBRID.value,
                    "lexical_candidates": retrieval_meta.get("lexical_candidates", 0),
                    "semantic_candidates": retrieval_meta.get("semantic_candidates", 0),
                    "semantic_chunk_hits": retrieval_meta.get("semantic_chunk_hits", 0),
                    "candidate_pool_size": candidate_pool_size,
                    "embedding_provider": embedding_chain.last_provider_used,
                    "timings_ms": retrieval_meta.get("timings_ms", {}),
                },
            },
            {
                "id": "reranking",
                "label": "Rerank the candidate pool",
                "duration_ms": rerank_ms,
                "details": {
                    "candidates_received": len(rerank_pool),
                    "candidates_sent_to_analysis": len(top_for_deep_analysis),
                    "provider": reranker_chain.last_provider_used,
                    "fallback_used": reranker_chain.last_fallback_used,
                },
            },
            {
                "id": "evidence_and_agents",
                "label": "Analyze requirements and validate resume evidence",
                "duration_ms": round(evidence_ms + analysis_ms, 2),
                "details": {
                    "evidence_load_ms": evidence_ms,
                    "candidates_analyzed": len(agent_states),
                    "agents": ["Candidate matching", "Skill gap", "Qualification", "Explainability and validation"],
                    "agent_handoffs": [
                        f"{route['from'].replace('_', ' ').title()} -> {route['to'].replace('_', ' ').title()}: {route['transfer_count']} candidate handoffs ({', '.join(route['artifacts'])})"
                        for route in handoff_routes.values()
                    ],
                    "handoff_count": sum(int(route["transfer_count"]) for route in handoff_routes.values()),
                    "handoffs_per_candidate": len(next(iter(agent_states.values())).handoff_history) if agent_states else 0,
                    "llm_providers": sorted(ai_providers_used),
                    "fallback_used": bool(llm_fallback_reasons),
                },
            },
            {
                "id": "final_ranking",
                "label": "Score candidates and select the shortlist",
                "duration_ms": ranking_ms,
                "details": {"candidates_scored": len(ranking_inputs), "top_n_requested": top_n, "results_returned": len(ranked)},
            },
        ]
    }

    search = Search(
        hr_user_id=hr_user_id,
        job_description_id=job.id if job else None,
        query_text=effective_query,
        extracted_requirements={
            "mandatory_skills": mandatory_skills,
            "preferred_skills": preferred_skills,
            "min_experience_years": min_years,
            "candidate_filters": applied_filters,
        },
        top_n_requested=top_n,
        retrieval_method=RetrievalMethod.HYBRID.value,
        resumes_considered=resumes_considered,
        candidate_pool_size=candidate_pool_size,
        processing_time_ms=processing_time_ms,
        fallback_used=any_fallback_used,
        fallback_reason="; ".join(sorted(set(fallback_reasons)))[:255] if fallback_reasons else None,
        ai_provider=", ".join(sorted(ai_providers_used)) if ai_providers_used else None,
        processing_mode=processing_mode,
        evaluation=retrieval_meta,
    )
    db.add(search)
    await db.flush()

    for rank_position, ranked_candidate in enumerate(ranked, start=1):
        candidate = candidates_by_id[ranked_candidate.candidate_id]
        state = agent_states[ranked_candidate.candidate_id]
        m, sg, ex = state.matching_result, state.skill_gap_result, state.explainability_result
        resume_id = candidate.resumes[-1].id if candidate.resumes else None

        def _finding_dict(f):
            return {
                "requirement": f.requirement,
                "requirement_type": f.requirement_type,
                "priority": f.priority,
                "status": f.status,
                "evidence_text": f.evidence_text,
                "page_number": f.page_number,
                "source_file": f.source_file,
                "note": f.note,
            }

        def _dedupe(findings):
            seen = set()
            deduped = []
            for f in findings:
                key = (f.requirement.lower(), f.requirement_type)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(f)
            return deduped

        unsupported_claims = {flag.claim for flag in ex.validation_notes}

        def has_validated_evidence(finding):
            return bool(finding.evidence_text) and f"{finding.requirement} ({finding.status})" not in unsupported_claims

        raw_matched = m.matched + sg.matched_skills
        raw_partial = sg.partial_skills
        unsupported_findings = [_as_unverified_missing(finding) for finding in raw_matched + raw_partial if not has_validated_evidence(finding)]
        matched_all = _dedupe([finding for finding in raw_matched if has_validated_evidence(finding)])
        partial_all = _dedupe([finding for finding in raw_partial if has_validated_evidence(finding)])
        missing_all = _dedupe(m.missing + sg.missing_skills + unsupported_findings)

        db.add(
            SearchCandidate(
                search_id=search.id,
                candidate_id=candidate.id,
                resume_id=resume_id,
                rank=rank_position,
                semantic_score=next((h.semantic_score for h in hybrid_hits if h.candidate_id == candidate.id), None),
                lexical_score=next((h.lexical_score for h in hybrid_hits if h.candidate_id == candidate.id), None),
                hybrid_retrieval_score=next((h.hybrid_score for h in hybrid_hits if h.candidate_id == candidate.id), None),
                reranker_score=normalized_rerank.get(candidate.id),
                final_score=ranked_candidate.final_score,
                score_breakdown=ranked_candidate.breakdown,
                matched_requirements=[_finding_dict(f) for f in matched_all],
                partial_requirements=[_finding_dict(f) for f in partial_all],
                missing_requirements=[_finding_dict(f) for f in missing_all],
                explanation_summary=ex.explanation_summary,
                explanation_points=ex.explanation_points,
                evidence=ex.top_evidence,
                validation_status=ex.validation_status,
                validation_notes=[{"claim": v.claim, "issue": v.issue} for v in ex.validation_notes],
            )
        )

    await db.commit()
    await db.refresh(search)
    return search
