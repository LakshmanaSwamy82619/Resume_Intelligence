from __future__ import annotations

import uuid

import pytest

from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.search import Search

pytestmark = pytest.mark.asyncio


async def test_admin_can_page_recorded_search_pipeline(client, admin_token):
    admin_id = decode_token(admin_token)["sub"]
    search_id = str(uuid.uuid4())
    stages = [{"id": "hybrid_retrieval", "label": "Retrieve profiles", "duration_ms": 12.5, "details": {"semantic_chunk_hits": 7}}]
    async with AsyncSessionLocal() as db:
        db.add(
            Search(
                id=search_id,
                hr_user_id=admin_id,
                query_text="Platform engineer with Kubernetes experience",
                top_n_requested=3,
                retrieval_method="hybrid",
                resumes_considered=80,
                candidate_pool_size=12,
                processing_time_ms=45.5,
                evaluation={"pipeline": {"stages": stages}, "providers": {"embedding": {"provider": "local"}}},
            )
        )
        await db.commit()

    response = await client.get("/api/v1/admin/searches?limit=25&offset=0", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    item = next(record for record in body["items"] if record["id"] == search_id)
    assert item["pipeline"]["stages"] == stages
    assert item["providers"]["embedding"]["provider"] == "local"
    assert item["guardrails"] == {
        "candidate_count": 0,
        "validated_candidates": 0,
        "flagged_candidates": 0,
        "validation_warnings": 0,
        "matched_requirements": 0,
        "matched_requirements_with_evidence": 0,
        "matched_requirements_without_evidence": 0,
    }
