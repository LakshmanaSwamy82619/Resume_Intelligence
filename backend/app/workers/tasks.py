"""
Background tasks (Section 26).

Bulk resume processing pipeline:

    Bulk upload -> ProcessingJob created (PENDING)
    -> queue via Celery -> worker picks up process_bulk_resumes
    -> for each file: extraction -> chunking -> embeddings -> indexing
    -> ProcessingJob updated to COMPLETED/PARTIAL/FAILED, with per-file
       error tracking and a completion notification/email to the uploader.

Each task creates its own asyncio event loop and DB session -- Celery
workers are synchronous processes, so async DB/provider calls are bridged
with asyncio.run() per task invocation, which is the standard, low-overhead
way to call async application code from a sync Celery task without pulling
in a separate async task runner.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.enums import ProcessingStatus
from app.models.search import ProcessingJob
from app.models.user import User
from app.services.email_service import processing_completed_body, send_email
from app.services.notification_service import create_notification
from app.services.resume_service import ingest_resume_file
from app.workers.celery_app import celery_app
from app.models.enums import NotificationType

logger = logging.getLogger("app.workers.tasks")
settings = get_settings()


@celery_app.task(name="tasks.send_email_task", bind=True, max_retries=3)
def send_email_task(self, to_email: str, subject: str, body: str):
    ok = send_email(to_email, subject, body)
    if not ok:
        raise self.retry(countdown=15)
    return ok


@celery_app.task(name="tasks.process_bulk_resumes", bind=True)
def process_bulk_resumes(self, processing_job_id: str, file_paths: list[str], uploaded_by_user_id: str):
    try:
        return asyncio.run(_process_bulk_resumes_async(processing_job_id, file_paths, uploaded_by_user_id))
    finally:
        _cleanup_bulk_files(file_paths)


async def _process_bulk_resumes_async(processing_job_id: str, file_paths: list[str], uploaded_by_user_id: str):
    async with AsyncSessionLocal() as db:
        job = await db.get(ProcessingJob, processing_job_id)
        if job is None:
            logger.error("processing_job_not_found", extra={"extra_fields": {"job_id": processing_job_id}})
            _cleanup_bulk_files(file_paths)
            return

        job.status = ProcessingStatus.PROCESSING.value
        job.total_items = len(file_paths)
        await db.commit()

        errors: list[dict] = []
        processed = 0
        failed = 0
        duplicates = 0

        for path in file_paths:
            filename = os.path.basename(path)
            mime_type = _guess_mime(filename)
            try:
                with open(path, "rb") as f:
                    file_bytes = f.read()
                _, is_duplicate = await ingest_resume_file(
                    db, file_bytes=file_bytes, original_filename=filename, mime_type=mime_type, uploaded_by_user_id=uploaded_by_user_id
                )
                if is_duplicate:
                    duplicates += 1
                processed += 1
            except Exception as exc:
                failed += 1
                errors.append({"file": filename, "error": str(exc)})
                logger.warning("bulk_resume_item_failed", extra={"extra_fields": {"file": filename, "error": str(exc)}})
            finally:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                job.processed_items = processed
                job.failed_items = failed
                job.duplicate_items = duplicates
                job.error_summary = errors[-50:]  # cap stored error detail
                await db.commit()

        if failed == 0:
            job.status = ProcessingStatus.COMPLETED.value
        elif processed > failed:
            job.status = ProcessingStatus.PARTIAL.value
        else:
            job.status = ProcessingStatus.FAILED.value
        await db.commit()

        uploader = await db.get(User, uploaded_by_user_id)
        if uploader:
            await create_notification(
                db, uploader.id, NotificationType.BULK_UPLOAD_COMPLETED,
                "Bulk resume upload finished",
                f"Processed {processed}/{len(file_paths)} resumes ({failed} failed, {duplicates} duplicates).",
            )
            send_email(
                uploader.email, "Bulk resume upload finished",
                processing_completed_body(uploader.full_name, len(file_paths), processed, failed),
            )
        _cleanup_bulk_files(file_paths)


def _cleanup_bulk_files(file_paths: list[str]) -> None:
    if not file_paths:
        return
    for path in file_paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    shutil.rmtree(os.path.dirname(file_paths[0]), ignore_errors=True)


def _guess_mime(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }.get(ext, "application/octet-stream")
