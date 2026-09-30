from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.candidate import Candidate, Resume
from app.models.user import User
from app.services.profile_completeness import profile_completeness

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


@router.get("")
async def list_candidates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=100),
    processing_status: str | None = Query(default=None, max_length=20),
    skill: str | None = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(or_(
            Candidate.full_name.ilike(pattern),
            Candidate.email.ilike(pattern),
            cast(Candidate.technical_skills, String).ilike(pattern),
            exists(select(Resume.id).where(
                Resume.candidate_id == Candidate.id,
                or_(Resume.original_filename.ilike(pattern), Resume.raw_text.ilike(pattern)),
            )),
        ))
    if skill and skill.strip():
        pattern = f"%{skill.strip()}%"
        conditions.append(or_(
            cast(Candidate.technical_skills, String).ilike(pattern),
            exists(select(Resume.id).where(Resume.candidate_id == Candidate.id, Resume.raw_text.ilike(pattern))),
        ))
    if category or processing_status:
        resume_conditions = [Resume.candidate_id == Candidate.id]
        if category:
            resume_conditions.append(Resume.source_category == category)
        if processing_status:
            resume_conditions.append(Resume.processing_status == processing_status)
        conditions.append(exists(select(Resume.id).where(*resume_conditions)))
    filtered_count_query = select(func.count(Candidate.id)).where(*conditions)
    total = (await db.execute(filtered_count_query)).scalar_one()
    total_resumes = (await db.execute(select(func.count(Resume.id)))).scalar_one()
    categories = (await db.execute(
        select(Resume.source_category).where(Resume.source_category.is_not(None)).distinct().order_by(Resume.source_category)
    )).scalars().all()
    processing_statuses = (await db.execute(
        select(Resume.processing_status).distinct().order_by(Resume.processing_status)
    )).scalars().all()
    stmt = (
        select(Candidate)
        .where(*conditions)
        .options(
            selectinload(Candidate.resumes), selectinload(Candidate.experience),
            selectinload(Candidate.projects), selectinload(Candidate.education),
            selectinload(Candidate.certifications),
        )
        .order_by(Candidate.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    candidates = result.scalars().all()

    def display_resume(candidate: Candidate):
        matching_resumes = [
            resume for resume in candidate.resumes
            if (not category or resume.source_category == category)
            and (not processing_status or resume.processing_status == processing_status)
        ]
        resumes = matching_resumes or candidate.resumes
        return max(resumes, key=lambda resume: resume.created_at) if resumes else None

    serialized_candidates = []
    for candidate in candidates:
        resume = display_resume(candidate)
        serialized_candidates.append({
            "candidate_id": candidate.id,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "technical_skills": candidate.technical_skills,
            "years_of_experience": candidate.years_of_experience,
            "category": resume.source_category if resume else None,
            "source_filename": resume.original_filename if resume else None,
            "processing_status": resume.processing_status if resume else None,
            "resume_count": len(candidate.resumes),
            "profile_completeness": profile_completeness(candidate),
        })

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_resumes": total_resumes,
        "categories": categories,
        "processing_statuses": processing_statuses,
        "items": serialized_candidates,
    }
