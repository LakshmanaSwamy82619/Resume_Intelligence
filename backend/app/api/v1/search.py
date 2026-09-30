from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from io import BytesIO, StringIO
import csv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_hr
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.job import JobDescription, JobRequirement
from app.models.search import Search, SearchCandidate
from app.models.user import User
from app.providers.llm.chain import LLMProviderChain
from app.schemas.search import (
    CandidateSearchResult,
    CompareCandidatesRequest,
    RequirementFindingResponse,
    SearchHistoryItem,
    SearchRequest,
    SearchResponse,
    ShortlistExportRequest,
)
from app.services.notification_service import record_audit_log
from app.services.search_service import run_search

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def _findings(items: list[dict]) -> list[RequirementFindingResponse]:
    return [RequirementFindingResponse(**item) for item in items]


async def _get_candidate_with_relations(db: AsyncSession, candidate_id: str) -> Candidate | None:
    stmt = (
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(selectinload(Candidate.experience), selectinload(Candidate.projects))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _to_response(db: AsyncSession, search: Search) -> SearchResponse:
    results = []
    ordered = sorted(search.candidates, key=lambda c: c.rank)
    for sc in ordered:
        candidate = await _get_candidate_with_relations(db, sc.candidate_id)
        results.append(
            CandidateSearchResult(
                rank=sc.rank,
                candidate_id=sc.candidate_id,
                candidate_name=candidate.full_name if candidate else None,
                resume_id=sc.resume_id,
                resume_download_url=f"/api/v1/resumes/{sc.resume_id}/download" if sc.resume_id else None,
                final_score=sc.final_score,
                score_breakdown=sc.score_breakdown,
                matched_requirements=_findings(sc.matched_requirements),
                partial_requirements=_findings(sc.partial_requirements),
                missing_requirements=_findings(sc.missing_requirements),
                years_of_experience=candidate.years_of_experience if candidate else None,
                relevant_projects=[{"name": p.name, "technologies": p.technologies} for p in (candidate.projects if candidate else [])],
                relevant_experience=[{"title": e.title, "company": e.company} for e in (candidate.experience if candidate else [])],
                why_selected_summary=sc.explanation_summary or "",
                why_selected_points=sc.explanation_points or [],
                evidence=sc.evidence or [],
                validation_status=sc.validation_status or "validated",
                validation_notes=sc.validation_notes or [],
            )
        )

    return SearchResponse(
        search_id=search.id,
        top_n_requested=search.top_n_requested,
        resumes_considered=search.resumes_considered,
        candidate_pool_size=search.candidate_pool_size,
        retrieval_method=search.retrieval_method,
        processing_time_ms=search.processing_time_ms,
        ai_provider=search.ai_provider,
        fallback_used=search.fallback_used,
        fallback_reason=search.fallback_reason,
        processing_mode=search.processing_mode,
        provider_status=(search.evaluation or {}).get("providers", {}),
        applied_filters=(search.extracted_requirements or {}).get("candidate_filters", {}),
        processing_pipeline=(search.evaluation or {}).get("pipeline", {}),
        results=results,
    )


@router.post("", response_model=SearchResponse)
async def create_search(payload: SearchRequest, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    job = None
    if payload.job_description_id:
        stmt = select(JobDescription).where(JobDescription.id == payload.job_description_id).options(selectinload(JobDescription.requirements))
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise NotFoundError("Job description not found.")
        if job.created_by_user_id != hr.id:
            raise NotFoundError("Job description not found.")

    search = await run_search(
        db, hr_user_id=hr.id, query_text=payload.resolve_query(), job=job, top_n=payload.top_n, llm_chain=LLMProviderChain(),
        candidate_filters=payload.candidate_filters.model_dump(exclude_none=True),
    )
    stmt = select(Search).where(Search.id == search.id).options(selectinload(Search.candidates))
    search = (await db.execute(stmt)).scalar_one()

    await record_audit_log(db, hr.id, "candidate_search", resource_type="search", resource_id=search.id, details={"top_n": payload.top_n})
    return await _to_response(db, search)


@router.get("", response_model=list[SearchHistoryItem])
async def search_history(hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db), limit: int = 50):
    stmt = select(Search).where(Search.hr_user_id == hr.id).order_by(Search.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(search_id: str, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    stmt = select(Search).where(Search.id == search_id).options(selectinload(Search.candidates))
    search = (await db.execute(stmt)).scalar_one_or_none()
    if not search:
        raise NotFoundError("Search not found.")
    if search.hr_user_id != hr.id:
        raise ForbiddenError("You do not have access to this search.")
    return await _to_response(db, search)


@router.post("/compare")
async def compare_candidates(payload: CompareCandidatesRequest, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    stmt = select(Search).where(Search.id == payload.search_id).options(selectinload(Search.candidates))
    search = (await db.execute(stmt)).scalar_one_or_none()
    if not search or search.hr_user_id != hr.id:
        raise NotFoundError("Search not found.")

    chosen = [sc for sc in search.candidates if sc.candidate_id in payload.candidate_ids]
    if len(chosen) < 2:
        raise NotFoundError("At least two of the requested candidates were not found in this search's results.")
    await record_audit_log(db, hr.id, "candidates_compared", resource_type="search", resource_id=search.id, details={"candidate_count": len(chosen)})

    comparison = []
    for sc in sorted(chosen, key=lambda c: c.rank):
        candidate = await db.get(Candidate, sc.candidate_id)
        comparison.append(
            {
                "candidate_id": sc.candidate_id,
                "candidate_name": candidate.full_name if candidate else None,
                "rank": sc.rank,
                "final_score": sc.final_score,
                "score_breakdown": sc.score_breakdown,
                "years_of_experience": candidate.years_of_experience if candidate else None,
                "matched_requirements": sc.matched_requirements,
                "partial_requirements": sc.partial_requirements,
                "missing_requirements": sc.missing_requirements,
                "why_selected_summary": sc.explanation_summary,
            }
        )
    requirement_items: dict[tuple[str, str], dict] = {}
    if search.job_description_id:
        job = (await db.execute(select(JobDescription).where(JobDescription.id == search.job_description_id).options(selectinload(JobDescription.requirements)))).scalar_one_or_none()
        if job:
            requirement_items = {
                (requirement.requirement_type, requirement.value.casefold()): {
                    "value": requirement.value,
                    "requirement_type": requirement.requirement_type,
                    "priority": requirement.priority,
                }
                for requirement in job.requirements
            }
    if not requirement_items:
        for candidate in comparison:
            for finding in [*candidate["matched_requirements"], *candidate["partial_requirements"], *candidate["missing_requirements"]]:
                key = (finding.get("requirement_type", "skill"), str(finding.get("requirement", "")).casefold())
                requirement_items.setdefault(key, {"value": finding.get("requirement", ""), "requirement_type": key[0], "priority": finding.get("priority", "preferred")})
    return {"search_id": search.id, "requirements": list(requirement_items.values()), "candidates": comparison}


@router.post("/{search_id}/export")
async def export_shortlist(search_id: str, payload: ShortlistExportRequest, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    stmt = select(Search).where(Search.id == search_id).options(selectinload(Search.candidates))
    search = (await db.execute(stmt)).scalar_one_or_none()
    if not search or search.hr_user_id != hr.id:
        raise NotFoundError("Search not found.")
    by_id = {candidate.candidate_id: candidate for candidate in search.candidates}
    if len(set(payload.candidate_ids)) != len(payload.candidate_ids) or any(candidate_id not in by_id for candidate_id in payload.candidate_ids):
        raise NotFoundError("One or more selected candidates are not in this search shortlist.")

    selected = [by_id[candidate_id] for candidate_id in payload.candidate_ids]
    await record_audit_log(db, hr.id, "shortlist_exported", resource_type="search", resource_id=search.id, details={"candidate_count": len(selected), "format": payload.format})
    candidate_rows = []
    for item in selected:
        candidate = await db.get(Candidate, item.candidate_id)
        candidate_rows.append((item, candidate))

    def safe_cell(value: object) -> str:
        text = str(value or "")
        return "'" + text if text.startswith(("=", "+", "-", "@")) else text

    if payload.format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Rank", "Candidate", "Candidate ID", "Score", "Years of experience", "Matched requirements", "Partial requirements", "Missing requirements", "Explanation", "Evidence"])
        for item, candidate in candidate_rows:
            def names(field: str) -> str:
                return "; ".join(str(entry.get("requirement", "")) for entry in (getattr(item, field) or []))
            evidence = " | ".join(str(entry.get("evidence_text", "")) for entry in (item.evidence or []))
            writer.writerow([item.rank, safe_cell(candidate.full_name if candidate else "Candidate"), item.candidate_id, round(item.final_score, 4), candidate.years_of_experience if candidate else "", safe_cell(names("matched_requirements")), safe_cell(names("partial_requirements")), safe_cell(names("missing_requirements")), safe_cell(item.explanation_summary), safe_cell(evidence)])
        content = output.getvalue().encode("utf-8-sig")
        return StreamingResponse(BytesIO(content), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="shortlist-{search_id[:8]}.csv"'})

    from app.services.export_service import shortlist_pdf
    content = shortlist_pdf(search.query_text, candidate_rows)
    return StreamingResponse(BytesIO(content), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="shortlist-{search_id[:8]}.pdf"'})
