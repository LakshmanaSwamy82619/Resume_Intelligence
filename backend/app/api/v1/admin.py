from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.enums import ProcessingStatus, UserRole
from app.models.candidate import Candidate, Resume
from app.models.search import Search
from app.models.user import AuditLog, User
from app.schemas.auth import CreateHrAccountRequest, UpdateAccountStatusRequest, UserResponse
from app.schemas.evaluation import AdminAnalyticsResponse, SystemHealthResponse
from app.services import auth_service
from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
settings = get_settings()


@router.post("/hr-accounts", response_model=UserResponse)
async def create_hr_account(payload: CreateHrAccountRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    user = await auth_service.create_hr_account(db, admin.id, payload.email, payload.full_name, payload.phone, payload.temporary_password)
    return user


@router.get("/hr-accounts", response_model=list[UserResponse])
async def list_hr_accounts(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.role == UserRole.HR.value).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.patch("/hr-accounts/{user_id}/status", response_model=UserResponse)
async def update_hr_account_status(user_id: str, payload: UpdateAccountStatusRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await auth_service.set_account_active(db, admin.id, user_id, payload.is_active)


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
    action: str | None = None, resource_type: str | None = None, user_id: str | None = None,
    from_date: date | None = None, to_date: date | None = None,
    q: str | None = Query(None, max_length=200),
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if from_date:
        filters.append(AuditLog.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        filters.append(AuditLog.created_at < datetime.combine(to_date + timedelta(days=1), time.min))
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            AuditLog.action.ilike(pattern), AuditLog.resource_type.ilike(pattern),
            AuditLog.resource_id.ilike(pattern), AuditLog.ip_address.ilike(pattern),
            cast(AuditLog.details, String).ilike(pattern), User.full_name.ilike(pattern), User.email.ilike(pattern),
        ))
    total = (await db.execute(
        select(func.count(AuditLog.id)).outerjoin(User, AuditLog.user_id == User.id).where(*filters)
    )).scalar_one()
    result = await db.execute(
        select(AuditLog).outerjoin(User, AuditLog.user_id == User.id).where(*filters)
        .order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    )
    entries = result.scalars().all()
    actor_ids = {entry.user_id for entry in entries if entry.user_id}
    actors = {}
    if actor_ids:
        actor_rows = (await db.execute(select(User.id, User.full_name, User.email).where(User.id.in_(actor_ids)))).all()
        actors = {row.id: {"name": row.full_name, "email": row.email} for row in actor_rows}
    actions = (await db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))).scalars().all()
    resource_types = (await db.execute(
        select(AuditLog.resource_type).where(AuditLog.resource_type.is_not(None)).distinct().order_by(AuditLog.resource_type)
    )).scalars().all()
    user_options = (await db.execute(
        select(User.id, User.full_name, User.email).join(AuditLog, AuditLog.user_id == User.id).distinct().order_by(User.full_name)
    )).all()
    return {
        "items": [{
            "id": entry.id, "user_id": entry.user_id,
            "user_name": actors.get(entry.user_id, {}).get("name"),
            "user_email": actors.get(entry.user_id, {}).get("email"),
            "action": entry.action, "resource_type": entry.resource_type, "resource_id": entry.resource_id,
            "created_at": entry.created_at, "ip_address": entry.ip_address, "details": entry.details or {},
        } for entry in entries],
        "total": total, "limit": limit, "offset": offset, "actions": actions, "resource_types": resource_types,
        "users": [{"id": row.id, "name": row.full_name, "email": row.email} for row in user_options],
    }


@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def analytics(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    total_resumes = (await db.execute(select(func.count(Resume.id)))).scalar_one()
    processed_resumes = (await db.execute(select(func.count(Resume.id)).where(Resume.processing_status == ProcessingStatus.COMPLETED.value))).scalar_one()
    partial_resumes = (await db.execute(select(func.count(Resume.id)).where(Resume.processing_status == ProcessingStatus.PARTIAL.value))).scalar_one()
    failed_resumes = (await db.execute(select(func.count(Resume.id)).where(Resume.processing_status == ProcessingStatus.FAILED.value))).scalar_one()
    pending_resumes = (await db.execute(select(func.count(Resume.id)).where(Resume.processing_status.in_([ProcessingStatus.PENDING.value, ProcessingStatus.PROCESSING.value])))).scalar_one()
    total_candidates = (await db.execute(select(func.count(Candidate.id)))).scalar_one()
    total_searches = (await db.execute(select(func.count(Search.id)))).scalar_one()
    top3_searches = (await db.execute(select(func.count(Search.id)).where(Search.top_n_requested == 3))).scalar_one()
    top5_searches = (await db.execute(select(func.count(Search.id)).where(Search.top_n_requested == 5))).scalar_one()
    total_hr = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.HR.value))).scalar_one()
    active_hr = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.HR.value, User.is_active.is_(True)))).scalar_one()
    fallback_count = (await db.execute(select(func.count(Search.id)).where(Search.fallback_used.is_(True)))).scalar_one()
    avg_latency = (await db.execute(select(func.avg(Search.processing_time_ms)))).scalar_one()

    return AdminAnalyticsResponse(
        total_resumes=total_resumes,
        processed_resumes=processed_resumes,
        partial_resumes=partial_resumes,
        failed_resumes=failed_resumes,
        pending_resumes=pending_resumes,
        total_candidates=total_candidates,
        total_searches=total_searches,
        top3_searches=top3_searches,
        top5_searches=top5_searches,
        total_hr_users=total_hr,
        active_hr_users=active_hr,
        fallback_usage_rate=round((fallback_count / total_searches), 4) if total_searches else 0.0,
        avg_search_latency_ms=round(avg_latency, 2) if avg_latency else None,
    )


@router.get("/retrieval-metrics")
async def retrieval_metrics(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Search.retrieval_method, Search.candidate_pool_size, Search.resumes_considered).order_by(Search.created_at.desc()).limit(100))
    rows = result.all()
    return [{"retrieval_method": r[0], "candidate_pool_size": r[1], "resumes_considered": r[2]} for r in rows]


@router.get("/searches")
async def search_pipeline_records(
    limit: int = 25,
    offset: int = 0,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated persisted searches with their recorded pipeline traces."""
    page_size = max(1, min(limit, 100))
    page_offset = max(0, offset)
    total = (await db.execute(select(func.count(Search.id)))).scalar_one()
    result = await db.execute(
        select(Search).options(selectinload(Search.candidates)).order_by(Search.created_at.desc()).offset(page_offset).limit(page_size)
    )
    searches = result.scalars().all()

    def guardrail_summary(search: Search) -> dict:
        candidates = search.candidates
        matched = [finding for candidate in candidates for finding in (candidate.matched_requirements or [])]
        return {
            "candidate_count": len(candidates),
            "validated_candidates": sum(1 for candidate in candidates if candidate.validation_status == "validated"),
            "flagged_candidates": sum(1 for candidate in candidates if candidate.validation_status == "flagged"),
            "validation_warnings": sum(len(candidate.validation_notes or []) for candidate in candidates),
            "matched_requirements": len(matched),
            "matched_requirements_with_evidence": sum(1 for finding in matched if finding.get("evidence_text")),
            "matched_requirements_without_evidence": sum(1 for finding in matched if not finding.get("evidence_text")),
        }

    return {
        "total": total,
        "limit": page_size,
        "offset": page_offset,
        "items": [
            {
                "id": search.id,
                "query_text": search.query_text,
                "created_at": search.created_at,
                "top_n_requested": search.top_n_requested,
                "retrieval_method": search.retrieval_method,
                "resumes_considered": search.resumes_considered,
                "candidate_pool_size": search.candidate_pool_size,
                "processing_time_ms": search.processing_time_ms,
                "fallback_used": search.fallback_used,
                "fallback_reason": search.fallback_reason,
                "ai_provider": search.ai_provider,
                "processing_mode": search.processing_mode,
                "extracted_requirements": search.extracted_requirements,
                "pipeline": (search.evaluation or {}).get("pipeline"),
                "providers": (search.evaluation or {}).get("providers", {}),
                "retrieval_meta": search.evaluation or {},
                "guardrails": guardrail_summary(search),
            }
            for search in searches
        ],
    }


@router.get("/system-health", response_model=SystemHealthResponse)
async def system_health(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.api.v1.health import _check_celery, _check_db, _check_redis

    db_ok = await _check_db(db)
    redis_ok = _check_redis()
    celery_ok = _check_celery() if redis_ok else False
    return SystemHealthResponse(
        status="ok" if db_ok and redis_ok and celery_ok else "degraded",
        database="ok" if db_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
        celery="ok" if celery_ok else "unavailable",
        llm_provider=settings.LLM_PROVIDER,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        reranker_provider=settings.RERANKER_PROVIDER,
    )
