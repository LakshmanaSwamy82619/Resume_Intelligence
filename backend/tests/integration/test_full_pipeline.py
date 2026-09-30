import pytest

pytestmark = pytest.mark.asyncio

STRONG_RESUME = b"""Alice Johnson
alice.johnson@example.com
+1-555-0100

Summary
Data scientist with a strong background in machine learning.

Skills
Python, SQL, Machine Learning, NLP, PyTorch, AWS

Experience
Machine Learning Engineer, Acme Analytics
Jan 2021 - Present
Built NLP models for ticket classification using Python and PyTorch. Used SQL pipelines on AWS.

Projects
Churn Prediction
Built a churn model using Python, Scikit-learn and SQL, deployed on AWS.

Education
B.Tech Computer Science, State University, 2019

Certifications
AWS Certified Machine Learning
"""

WEAK_RESUME = b"""Bob Smith
bob.smith@example.com
+1-555-0200

Summary
Frontend developer.

Skills
JavaScript, React, HTML, CSS

Experience
Frontend Developer, WebWorks Inc
Mar 2022 - Present
Built React components using JavaScript and CSS.

Education
B.A. Design, City College, 2021
"""


async def test_full_search_pipeline_ranks_relevant_candidate_first(client, hr_token):
    headers = {"Authorization": f"Bearer {hr_token}"}

    uploaded = []
    for filename, content in [("alice.txt", STRONG_RESUME), ("bob.txt", WEAK_RESUME)]:
        r = await client.post("/api/v1/resumes/upload", headers=headers, files={"file": (filename, content, "text/plain")})
        assert r.status_code == 200, r.text
        assert r.json()["processing_status"] == "completed"
        uploaded.append(r.json())

    candidates = await client.get("/api/v1/candidates?page=1&page_size=10", headers=headers)
    assert candidates.status_code == 200
    listed = next(item for item in candidates.json()["items"] if item["candidate_id"] == uploaded[0]["candidate_id"])
    assert listed["source_filename"] == "alice.txt"
    assert listed["processing_status"] == "completed"
    detail = await client.get(f"/api/v1/resumes/candidates/{uploaded[0]['candidate_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["source_filename"] == "alice.txt"
    assert detail.json()["processing_status"] == "completed"
    assert detail.json()["resumes"][0]["source_filename"] == "alice.txt"
    assert detail.json()["resumes"][0]["category"] is None
    assert "source_relative_path" not in detail.json()

    r = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "raw_text": "Data Scientist role. Must have Python and SQL. At least 3 years of experience. "
            "Machine learning and NLP project experience required. AWS experience is a plus.",
            "input_mode": "pasted",
        },
    )
    assert r.status_code == 200, r.text
    job = r.json()
    assert "python" in [x["value"] for x in job["mandatory_requirements"]]
    assert job["min_experience_years"] == 3.0

    r = await client.post("/api/v1/search", headers=headers, json={"job_description_id": job["id"], "top_n": 3})
    assert r.status_code == 200, r.text
    result = r.json()

    assert result["resumes_considered"] >= 2
    assert len(result["results"]) >= 1
    assert set(result["provider_status"]) == {"embedding", "reranker", "llm"}
    assert "fallback_used" in result["provider_status"]["embedding"]
    assert "fallback_used" in result["provider_status"]["reranker"]
    assert "fallback_used" in result["provider_status"]["llm"]

    top = result["results"][0]
    assert top["candidate_name"] == "Alice Johnson"
    assert top["rank"] == 1
    assert any(m["requirement"] == "python" for m in top["matched_requirements"])
    assert top["why_selected_summary"]  # explanation must not be empty
    assert top["evidence"]  # evidence must be present and non-fabricated
    assert all(item["source_file"] and item["page_number"] for item in top["evidence"])
    assert all(item["evidence_text"] in STRONG_RESUME.decode("utf-8") for item in top["evidence"])

    # No fabricated LLM claims possible here since LLM_PROVIDER=none in tests;
    # validation should still succeed because every matched claim carries evidence.
    assert top["validation_status"] in ("validated", "flagged")

    # Every matched requirement claim must carry a real evidence pointer
    # (Section 7/16.4 - no unsupported claims).
    for finding in top["matched_requirements"]:
        assert finding["evidence_text"], f"Matched requirement '{finding['requirement']}' has no evidence."


async def test_search_requires_job_description_or_query(client, hr_token):
    headers = {"Authorization": f"Bearer {hr_token}"}
    r = await client.post("/api/v1/search", headers=headers, json={"top_n": 3})
    assert r.status_code in (400, 422)


async def test_hr_cannot_access_admin_routes(client, hr_token):
    headers = {"Authorization": f"Bearer {hr_token}"}
    r = await client.get("/api/v1/admin/analytics", headers=headers)
    assert r.status_code == 403


async def test_search_history_and_evaluation_endpoints(client, hr_token, admin_token):
    headers = {"Authorization": f"Bearer {hr_token}"}
    await client.post("/api/v1/resumes/upload", headers=headers, files={"file": ("alice2.txt", STRONG_RESUME, "text/plain")})

    r = await client.post("/api/v1/search", headers=headers, json={"query_text": "Python developer with SQL experience", "top_n": 3})
    assert r.status_code == 200, r.text
    search_id = r.json()["search_id"]

    r = await client.get("/api/v1/hr/searches", headers=headers)
    assert r.status_code == 200
    assert any(s["id"] == search_id for s in r.json())

    r = await client.get(f"/api/v1/hr/searches/{search_id}/evaluation", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "evidence_coverage" in body
    assert "fallback_status" in body
    assert set(body["retrieval_meta"]["providers"]) == {"embedding", "reranker", "llm"}

    admin_response = await client.get("/api/v1/admin/searches?limit=25&offset=0", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_response.status_code == 200, admin_response.text
    trace = next(item for item in admin_response.json()["items"] if item["id"] == search_id)
    stages = trace["pipeline"]["stages"]
    assert [stage["id"] for stage in stages] == ["requirements", "candidate_corpus", "hybrid_retrieval", "reranking", "evidence_and_agents", "final_ranking"]
    retrieval = next(stage for stage in stages if stage["id"] == "hybrid_retrieval")
    assert "semantic_chunk_hits" in retrieval["details"]


async def test_job_response_reports_successful_llm_enrichment(client, hr_token, monkeypatch):
    from app.api.v1 import jobs
    from app.providers.llm.base import LLMResult

    class EnrichedChain:
        async def complete(self, *_args, **_kwargs):
            return LLMResult(
                text='{"title":"Enriched Engineer","domain":"data","mandatory_terms":["python"],"preferred_terms":[]}',
                provider="test-provider",
                model_used="test-model",
                fallback_used=False,
            )

    monkeypatch.setattr(jobs, "LLMProviderChain", EnrichedChain)
    response = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"raw_text": "Python engineer required for data pipelines.", "input_mode": "pasted"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["llm_enrichment_used"] is True
    assert response.json()["title"] == "Enriched Engineer"


async def test_job_response_reports_rule_fallback_without_llm_enrichment(client, hr_token, monkeypatch):
    from app.api.v1 import jobs
    from app.providers.llm.base import LLMResult

    class FallbackChain:
        async def complete(self, *_args, **_kwargs):
            return LLMResult(
                text="",
                provider="deterministic",
                model_used=None,
                fallback_used=True,
                fallback_reason="provider unavailable",
            )

    monkeypatch.setattr(jobs, "LLMProviderChain", FallbackChain)
    response = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"raw_text": "Python engineer required for data pipelines.", "input_mode": "pasted"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["llm_enrichment_used"] is False
