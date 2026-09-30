from __future__ import annotations

import os

import pytest

from app.api.v1 import resumes
from app.db.session import AsyncSessionLocal
from app.models.search import ProcessingJob
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def test_single_upload_rejects_oversize_before_document_processing(client, hr_token, monkeypatch):
    monkeypatch.setattr(resumes.settings, "MAX_UPLOAD_MB", 1)
    response = await client.post(
        "/api/v1/resumes/upload",
        headers={"Authorization": f"Bearer {hr_token}"},
        files={"file": ("large.txt", b"x" * (1024 * 1024 + 100), "text/plain")},
    )
    assert response.status_code == 422


async def test_bulk_upload_enforces_file_count_limit(client, hr_token):
    files = [("files", (f"resume-{i}.txt", b"", "text/plain")) for i in range(101)]
    response = await client.post("/api/v1/resumes/bulk-upload", headers={"Authorization": f"Bearer {hr_token}"}, files=files)
    assert response.status_code == 422


async def test_bulk_upload_enforces_aggregate_limit_and_cleans_partial_files(client, hr_token, monkeypatch):
    monkeypatch.setattr(resumes.settings, "MAX_UPLOAD_MB", 1)
    monkeypatch.setattr(resumes.settings, "MAX_BULK_UPLOAD_MB", 1)
    tmp_root = os.path.join(resumes.settings.UPLOAD_DIR, "bulk_tmp")
    before = set(os.listdir(tmp_root)) if os.path.isdir(tmp_root) else set()
    async with AsyncSessionLocal() as db:
        before_jobs = (await db.execute(select(ProcessingJob.id))).scalars().all()

    files = [
        ("files", ("first.txt", b"a" * 600_000, "text/plain")),
        ("files", ("second.txt", b"b" * 600_000, "text/plain")),
    ]
    response = await client.post("/api/v1/resumes/bulk-upload", headers={"Authorization": f"Bearer {hr_token}"}, files=files)
    assert response.status_code == 422
    assert (set(os.listdir(tmp_root)) if os.path.isdir(tmp_root) else set()) == before
    async with AsyncSessionLocal() as db:
        after_jobs = (await db.execute(select(ProcessingJob.id))).scalars().all()
    assert after_jobs == before_jobs


async def test_bulk_upload_runs_eager_task_and_updates_job_status(client, hr_token):
    response = await client.post(
        "/api/v1/resumes/bulk-upload",
        headers={"Authorization": f"Bearer {hr_token}"},
        files=[("files", ("eager-bulk.txt", b"Robin Example\nSkills\nPython", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["processing_job_id"]
    status = await client.get(
        f"/api/v1/resumes/bulk-upload/{job_id}",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "completed"
    assert status.json()["processed_items"] == 1
