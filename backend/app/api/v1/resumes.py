from __future__ import annotations

import os
import shutil
import uuid

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_hr
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, ProviderUnavailableError, ValidationAppError
from app.db.session import get_db
from app.models.candidate import Candidate, Resume
from app.models.enums import ProcessingStatus
from app.models.search import ProcessingJob
from app.models.user import User
from app.schemas.resume import BulkUploadResponse, CandidateDetailResponse, ProcessingJobStatusResponse, ResumeUploadResponse
from app.services.notification_service import record_audit_log
from app.services.profile_completeness import profile_completeness
from app.services.resume_service import ingest_resume_file, read_upload_limited
from app.workers.tasks import _process_bulk_resumes_async, process_bulk_resumes

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])
settings = get_settings()


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...), hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    file_bytes = await read_upload_limited(file, settings.MAX_UPLOAD_MB * 1024 * 1024)
    resume, is_duplicate = await ingest_resume_file(
        db, file_bytes=file_bytes, original_filename=file.filename, mime_type=file.content_type, uploaded_by_user_id=hr.id
    )
    await record_audit_log(db, hr.id, "resume_upload", resource_type="resume", resource_id=resume.id, details={"is_duplicate": is_duplicate})
    return ResumeUploadResponse(
        resume_id=resume.id,
        candidate_id=resume.candidate_id,
        processing_status=resume.processing_status,
        is_duplicate=is_duplicate,
        message="Duplicate of an existing resume; not re-indexed." if is_duplicate else "Resume processed successfully.",
    )


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_resumes(files: list[UploadFile] = File(...), hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    if not files:
        raise ValidationAppError("At least one resume file is required.")
    if len(files) > settings.MAX_BULK_FILES:
        raise ValidationAppError(f"Bulk upload exceeds the {settings.MAX_BULK_FILES}-file limit.")

    tmp_dir = os.path.join(settings.UPLOAD_DIR, "bulk_tmp", uuid.uuid4().hex)
    os.makedirs(tmp_dir, exist_ok=True)

    saved_paths = []
    aggregate_limit = settings.MAX_BULK_UPLOAD_MB * 1024 * 1024
    aggregate_bytes = 0
    try:
        for f in files:
            remaining = aggregate_limit - aggregate_bytes
            allowed = min(settings.MAX_UPLOAD_MB * 1024 * 1024, remaining)
            content = await read_upload_limited(f, allowed)
            aggregate_bytes += len(content)
            safe_name = f"{uuid.uuid4().hex}_{os.path.basename(f.filename or 'resume')}"
            path = os.path.join(tmp_dir, safe_name)
            with open(path, "wb") as out:
                out.write(content)
            saved_paths.append(path)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    job = ProcessingJob(job_type="bulk_resume", created_by_user_id=hr.id, status=ProcessingStatus.PENDING.value, total_items=len(saved_paths))
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if settings.CELERY_TASK_ALWAYS_EAGER:
        try:
            await _process_bulk_resumes_async(job.id, saved_paths, hr.id)
        except Exception as exc:
            job.status = ProcessingStatus.FAILED.value
            job.error_summary = [{"error": "Inline bulk processing failed; uploaded temporary files were removed."}]
            await db.commit()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ProviderUnavailableError("Bulk resume processing failed.") from exc
        job.celery_task_id = None
    else:
        try:
            async_result = process_bulk_resumes.delay(job.id, saved_paths, hr.id)
        except Exception as exc:
            job.status = ProcessingStatus.FAILED.value
            job.error_summary = [{"error": "Background queue unavailable; uploaded temporary files were removed."}]
            await db.commit()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ProviderUnavailableError("Background resume processing is unavailable.") from exc
        job.celery_task_id = async_result.id
    await db.commit()

    await record_audit_log(db, hr.id, "bulk_resume_upload", resource_type="processing_job", resource_id=job.id, details={"file_count": len(files)})

    message = "Bulk upload processed inline." if settings.CELERY_TASK_ALWAYS_EAGER else "Bulk upload queued for background processing."
    return BulkUploadResponse(processing_job_id=job.id, total_files=len(files), message=message)


@router.get("/bulk-upload/{job_id}", response_model=ProcessingJobStatusResponse)
async def get_bulk_upload_status(job_id: str, hr: User = Depends(require_hr), db: AsyncSession = Depends(get_db)):
    job = await db.get(ProcessingJob, job_id)
    if not job:
        raise NotFoundError("Processing job not found.")
    if job.created_by_user_id != hr.id:
        raise NotFoundError("Processing job not found.")
    return job


@router.get("/candidates/{candidate_id}", response_model=CandidateDetailResponse)
async def get_candidate_detail(candidate_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            selectinload(Candidate.experience),
            selectinload(Candidate.projects),
            selectinload(Candidate.education),
            selectinload(Candidate.certifications),
            selectinload(Candidate.resumes),
        )
    )
    candidate = (await db.execute(stmt)).scalar_one_or_none()
    if not candidate:
        raise NotFoundError("Candidate not found.")
    if user.role == "hr":
        await record_audit_log(db, user.id, "candidate_profile_viewed", resource_type="candidate", resource_id=candidate_id)

    latest_resume = max(candidate.resumes, key=lambda resume: resume.created_at) if candidate.resumes else None

    return CandidateDetailResponse(
        candidate_id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        summary=candidate.summary,
        technical_skills=candidate.technical_skills,
        soft_skills=candidate.soft_skills,
        job_titles=candidate.job_titles,
        years_of_experience=candidate.years_of_experience,
        profile_completeness=profile_completeness(candidate),
        experience=[{"company": e.company, "title": e.title, "start_date": e.start_date, "end_date": e.end_date} for e in candidate.experience],
        projects=[{"name": p.name, "technologies": p.technologies} for p in candidate.projects],
        education=[{"degree": e.degree, "institution": e.institution, "end_year": e.end_year} for e in candidate.education],
        certifications=[{"name": c.name} for c in candidate.certifications],
        source_filename=latest_resume.original_filename if latest_resume else None,
        category=latest_resume.source_category if latest_resume else None,
        processing_status=latest_resume.processing_status if latest_resume else None,
        resumes=[
            {
                "resume_id": resume.id,
                "source_filename": resume.original_filename,
                "category": resume.source_category,
                "processing_status": resume.processing_status,
                "resume_download_url": f"/api/v1/resumes/{resume.id}/download",
            }
            for resume in sorted(candidate.resumes, key=lambda item: item.created_at, reverse=True)
        ],
        resume_download_url=f"/api/v1/resumes/{latest_resume.id}/download" if latest_resume else None,
    )


@router.get("/{resume_id}/download")
async def download_resume(resume_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resume = await db.get(Resume, resume_id)
    if not resume or not os.path.exists(resume.storage_path):
        raise NotFoundError("Resume file not found.")
    await record_audit_log(db, user.id, "resume_downloaded", resource_type="resume", resource_id=resume.id)
    return FileResponse(resume.storage_path, filename=resume.original_filename, media_type=resume.mime_type)
