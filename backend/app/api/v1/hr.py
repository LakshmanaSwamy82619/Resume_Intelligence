"""
HR evaluation/search-tracking dashboard APIs (Section 24).

The spec's Section 24 example paths are unversioned (/api/hr/searches);
Section 36 asks for API versioning (/api/v1/...). We follow the versioning
convention consistently across the whole API and expose these same
capabilities at /api/v1/hr/... -- same route shapes and semantics, just
version-prefixed like every other module.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_hr
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.search import Search
from app.models.user import User

router = APIRouter(prefix="/api/v1/hr", tags=["hr-dashboard"])


@router.get("/overview")
async def workspace_overview(hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    totals = (await db.execute(
        select(func.count(Search.id), func.avg(Search.processing_time_ms)).where(Search.hr_user_id == hr.id)
    )).one()
    latest = (await db.execute(
        select(Search.candidate_pool_size)
        .where(Search.hr_user_id == hr.id)
        .order_by(Search.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    recent = (await db.execute(
        select(Search).where(Search.hr_user_id == hr.id).order_by(Search.created_at.desc()).limit(8)
    )).scalars().all()
    search_dates = (await db.execute(
        select(Search.created_at).where(Search.hr_user_id == hr.id).order_by(Search.created_at.asc())
    )).scalars().all()
    return {
        "total_searches": totals[0],
        "average_search_time_ms": round(totals[1], 2) if totals[1] is not None else None,
        "latest_result_pool": latest,
        "search_activity": search_dates,
        "recent_searches": [
            {
                "id": search.id,
                "query_text": search.query_text,
                "top_n_requested": search.top_n_requested,
                "resumes_considered": search.resumes_considered,
                "candidate_pool_size": search.candidate_pool_size,
                "processing_time_ms": search.processing_time_ms,
                "fallback_used": search.fallback_used,
                "created_at": search.created_at,
            }
            for search in recent
        ],
    }


@router.get("/searches")
async def list_searches(hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db), limit: int = 50):
    stmt = select(Search).where(Search.hr_user_id == hr.id).order_by(Search.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [
        {
            "id": s.id,
            "query_text": s.query_text,
            "top_n_requested": s.top_n_requested,
            "resumes_considered": s.resumes_considered,
            "candidate_pool_size": s.candidate_pool_size,
            "processing_time_ms": s.processing_time_ms,
            "fallback_used": s.fallback_used,
            "created_at": s.created_at,
        }
        for s in result.scalars().all()
    ]


async def _get_owned_search(db: AsyncSession, hr: User, search_id: str) -> Search:
    stmt = select(Search).where(Search.id == search_id).options(selectinload(Search.candidates))
    search = (await db.execute(stmt)).scalar_one_or_none()
    if not search:
        raise NotFoundError("Search not found.")
    if search.hr_user_id != hr.id:
        raise ForbiddenError("You do not have access to this search.")
    return search


@router.get("/searches/{search_id}")
async def get_search_detail(search_id: str, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    search = await _get_owned_search(db, hr, search_id)
    return {
        "id": search.id,
        "query_text": search.query_text,
        "extracted_requirements": search.extracted_requirements,
        "top_n_requested": search.top_n_requested,
        "retrieval_method": search.retrieval_method,
        "resumes_considered": search.resumes_considered,
        "candidate_pool_size": search.candidate_pool_size,
        "processing_time_ms": search.processing_time_ms,
        "fallback_used": search.fallback_used,
        "fallback_reason": search.fallback_reason,
        "ai_provider": search.ai_provider,
        "processing_mode": search.processing_mode,
        "created_at": search.created_at,
    }


@router.get("/searches/{search_id}/candidates")
async def get_search_candidates(search_id: str, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    search = await _get_owned_search(db, hr, search_id)
    return [
        {
            "rank": sc.rank,
            "candidate_id": sc.candidate_id,
            "final_score": sc.final_score,
            "matched_requirements": sc.matched_requirements,
            "partial_requirements": sc.partial_requirements,
            "missing_requirements": sc.missing_requirements,
            "validation_status": sc.validation_status,
        }
        for sc in sorted(search.candidates, key=lambda c: c.rank)
    ]


@router.get("/searches/{search_id}/evaluation")
async def get_search_evaluation(search_id: str, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    search = await _get_owned_search(db, hr, search_id)
    evidence_backed = sum(1 for sc in search.candidates for r in sc.matched_requirements if r.get("evidence_text"))
    total_matched = sum(len(sc.matched_requirements) for sc in search.candidates)
    return {
        "search_id": search.id,
        "search_latency_ms": search.processing_time_ms,
        "candidates_retrieved": search.candidate_pool_size,
        "top_n_returned": len(search.candidates),
        "fallback_status": {
            "fallback_used": search.fallback_used,
            "fallback_reason": search.fallback_reason,
            "ai_provider": search.ai_provider,
            "processing_mode": search.processing_mode,
        },
        "evidence_coverage": {
            "matched_requirements_with_evidence": evidence_backed,
            "total_matched_requirements": total_matched,
            "coverage_rate": round(evidence_backed / total_matched, 4) if total_matched else None,
        },
        "retrieval_meta": search.evaluation,
    }
