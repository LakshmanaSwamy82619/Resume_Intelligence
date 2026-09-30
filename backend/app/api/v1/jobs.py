from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.api.deps import require_hr
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.job import JobDescription, JobRequirement
from app.models.user import User
from app.providers.llm.chain import LLMProviderChain
from app.schemas.search import JobDescriptionCreateRequest, JobDescriptionResponse, JobRequirementsUpdateRequest
from app.ingestion.parsers import parse_document
from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.services.resume_service import read_upload_limited, validate_upload
from app.services.job_service import create_job_description, split_requirements
from app.services.notification_service import record_audit_log

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _to_response(job: JobDescription) -> JobDescriptionResponse:
    mandatory, preferred = split_requirements(job)
    return JobDescriptionResponse(
        id=job.id,
        title=job.title,
        raw_text=job.raw_text,
        input_mode=job.input_mode,
        source_filename=job.source_filename,
        mandatory_requirements=[{"type": r.requirement_type, "value": r.value} for r in mandatory],
        preferred_requirements=[{"type": r.requirement_type, "value": r.value} for r in preferred],
        min_experience_years=job.min_experience_years,
        preferred_experience_years=job.preferred_experience_years,
        llm_enrichment_used=job.llm_enrichment_used,
        created_at=job.created_at,
    )


@router.post("", response_model=JobDescriptionResponse)
async def create_job(payload: JobDescriptionCreateRequest, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    job = await create_job_description(db, hr.id, payload.raw_text, payload.title, payload.input_mode, LLMProviderChain())
    await record_audit_log(db, hr.id, "job_brief_created", resource_type="job_brief", resource_id=job.id, details={"input_mode": payload.input_mode})
    stmt = select(JobDescription).where(JobDescription.id == job.id).options(selectinload(JobDescription.requirements))
    job = (await db.execute(stmt)).scalar_one()
    return _to_response(job)


@router.post("/upload", response_model=JobDescriptionResponse)
async def upload_job_description(
    file: UploadFile = File(...), title: str | None = Form(None),
    hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db),
):
    filename = file.filename or "job-description.txt"
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mime_by_suffix = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "txt": "text/plain"}
    mime_type = mime_by_suffix.get(suffix, file.content_type or "application/octet-stream")
    max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    content = await read_upload_limited(file, max_bytes)
    validate_upload(filename, mime_type, len(content))
    parsed = parse_document(content, mime_type, filename)
    raw_text = parsed.full_text.strip()
    if len(raw_text) < 10:
        raise ValidationAppError("The uploaded job description must contain at least 10 readable characters.")
    job = await create_job_description(db, hr.id, raw_text, title, "uploaded", LLMProviderChain(), source_filename=filename)
    await record_audit_log(db, hr.id, "job_brief_uploaded", resource_type="job_brief", resource_id=job.id, details={"filename": filename})
    stmt = select(JobDescription).where(JobDescription.id == job.id).options(selectinload(JobDescription.requirements))
    return _to_response((await db.execute(stmt)).scalar_one())


@router.get("", response_model=list[JobDescriptionResponse])
async def list_jobs(hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(JobDescription)
        .where(JobDescription.created_by_user_id == hr.id)
        .options(selectinload(JobDescription.requirements))
        .order_by(JobDescription.created_at.desc())
    )
    result = await db.execute(stmt)
    return [_to_response(job) for job in result.scalars().unique().all()]


@router.get("/{job_id}", response_model=JobDescriptionResponse)
async def get_job(job_id: str, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    stmt = select(JobDescription).where(JobDescription.id == job_id).options(selectinload(JobDescription.requirements))
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise NotFoundError("Job description not found.")
    if job.created_by_user_id != hr.id:
        raise NotFoundError("Job description not found.")
    return _to_response(job)


@router.put("/{job_id}/requirements", response_model=JobDescriptionResponse)
async def update_job_requirements(
    job_id: str,
    payload: JobRequirementsUpdateRequest,
    hr: User = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(JobDescription).where(JobDescription.id == job_id).options(selectinload(JobDescription.requirements))
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job or job.created_by_user_id != hr.id:
        raise NotFoundError("Job description not found.")
    deduplicated: dict[tuple[str, str], object] = {}
    for requirement in payload.requirements:
        value = requirement.value.strip()
        if value:
            deduplicated[(requirement.requirement_type, value.casefold())] = requirement.model_copy(update={"value": value})
    job.requirements.clear()
    for requirement in deduplicated.values():
        db.add(JobRequirement(
            job_description_id=job.id,
            requirement_type=requirement.requirement_type,
            value=requirement.value,
            priority=requirement.priority,
        ))
    await db.commit()
    await record_audit_log(db, hr.id, "job_requirements_updated", resource_type="job_brief", resource_id=job.id, details={"requirement_count": len(deduplicated)})
    stmt = select(JobDescription).where(JobDescription.id == job.id).options(selectinload(JobDescription.requirements))
    return _to_response((await db.execute(stmt)).scalar_one())
