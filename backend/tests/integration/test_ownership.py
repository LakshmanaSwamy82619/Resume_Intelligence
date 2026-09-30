from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import ProcessingStatus, UserRole
from app.models.search import EvaluationDataset, EvaluationQuery, ProcessingJob
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _other_hr_token() -> str:
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"other-hr-{uuid.uuid4().hex}@example.com",
            hashed_password=hash_password("OtherPass123!"),
            full_name="Other Recruiter",
            role=UserRole.HR.value,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        token = create_access_token(user.id, user.role)
        await db.commit()
        return token


async def test_shared_candidate_pool_allows_cross_hr_candidate_and_resume_access(client, hr_token):
    other_token = await _other_hr_token()
    content = b"Morgan Data\nmorgan@example.com\nSkills\nPython, SQL"
    uploaded = await client.post(
        "/api/v1/resumes/upload",
        headers={"Authorization": f"Bearer {hr_token}"},
        files={"file": ("morgan.txt", content, "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    candidate_id = uploaded.json()["candidate_id"]
    resume_id = uploaded.json()["resume_id"]

    detail = await client.get(
        f"/api/v1/resumes/candidates/{candidate_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert detail.status_code == 200
    downloaded = await client.get(
        f"/api/v1/resumes/{resume_id}/download",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert downloaded.status_code == 200
    assert downloaded.content == content


async def test_jobs_are_private_to_creating_hr_and_cannot_be_used_cross_account(client, hr_token):
    other_token = await _other_hr_token()
    created = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"raw_text": "Python engineer required for data pipelines.", "input_mode": "pasted"},
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]

    hidden = await client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert hidden.status_code == 404
    search = await client.post(
        "/api/v1/search",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"job_description_id": job_id, "top_n": 3},
    )
    assert search.status_code == 404


async def test_bulk_jobs_are_private_to_creating_hr(client, hr_token):
    other_token = await _other_hr_token()
    from app.core.security import decode_token

    async with AsyncSessionLocal() as db:
        owner_id = decode_token(hr_token)["sub"]
        row = ProcessingJob(
            job_type="bulk_resume",
            created_by_user_id=owner_id,
            status=ProcessingStatus.PENDING.value,
            total_items=1,
        )
        db.add(row)
        await db.commit()
        job_id = row.id

    owned = await client.get(f"/api/v1/resumes/bulk-upload/{job_id}", headers={"Authorization": f"Bearer {hr_token}"})
    hidden = await client.get(f"/api/v1/resumes/bulk-upload/{job_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert owned.status_code == 200
    assert hidden.status_code == 404


async def test_evaluation_datasets_and_queries_are_private_to_creating_hr(client, hr_token):
    other_token = await _other_hr_token()
    created = await client.post(
        "/api/v1/evaluation/datasets",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"name": "private dataset"},
    )
    assert created.status_code == 200
    dataset_id = created.json()["id"]
    query = await client.post(
        f"/api/v1/evaluation/datasets/{dataset_id}/queries",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"query_text": "Python data engineer"},
    )
    assert query.status_code == 200
    query_id = query.json()["id"]

    get_hidden = await client.get(
        f"/api/v1/evaluation/datasets/{dataset_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    query_hidden = await client.post(
        f"/api/v1/evaluation/datasets/{dataset_id}/queries",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"query_text": "attempted cross-owner query"},
    )
    label_hidden = await client.post(
        f"/api/v1/evaluation/queries/{query_id}/labels",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"candidate_id": "no-access", "relevance": 1},
    )
    assert get_hidden.status_code == 404
    assert query_hidden.status_code == 404
    assert label_hidden.status_code == 404
