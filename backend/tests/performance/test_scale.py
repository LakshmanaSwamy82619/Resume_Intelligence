"""
Performance / scale tests (Section 39/41).

Honest status: this sandbox has no live Postgres+pgvector instance, so the
tests below run against the bundled SQLite brute-force vector search path
and are skipped by default -- they are provided as a ready-to-run harness
for the environment described in README ("How to test" -> performance),
not as evidence that 10,000-resume retrieval has been measured here.

To actually validate the 10,000+ resume target:
  1. `docker compose up -d postgres redis`
  2. `alembic upgrade head` against that Postgres instance
  3. Set RUN_PERFORMANCE_TESTS=1 and re-run pytest -- this generates N
     synthetic resumes directly into the DB (bypassing file parsing, which
     is already covered by ingestion unit tests) and times hybrid_retrieve.
"""
import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_PERFORMANCE_TESTS") != "1",
    reason="Performance tests are opt-in (RUN_PERFORMANCE_TESTS=1) and expect a real Postgres+pgvector instance.",
)


@pytest.mark.parametrize("resume_count", [100, 500, 1000, 10000])
async def test_hybrid_retrieval_latency_at_scale(resume_count, client, hr_token):
    """Seeds `resume_count` synthetic candidates directly via the DB layer
    (not through file upload, to isolate retrieval latency from parsing
    latency) and asserts hybrid retrieval completes in bounded time.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.candidate import Candidate

    async with AsyncSessionLocal() as db:
        for i in range(resume_count):
            db.add(
                Candidate(
                    full_name=f"Synthetic Candidate {i}",
                    email=f"synthetic{i}@example.com",
                    technical_skills=["python", "sql"] if i % 3 == 0 else ["java", "spring"],
                    years_of_experience=float(i % 10),
                )
            )
        await db.commit()

    headers = {"Authorization": f"Bearer {hr_token}"}
    start = time.perf_counter()
    r = await client.post("/api/v1/search", headers=headers, json={"query_text": "Python and SQL developer", "top_n": 5})
    elapsed = time.perf_counter() - start

    assert r.status_code == 200
    # Generous bound for CI variance -- the point of this test is a
    # regression guardrail, not a formal SLA.
    assert elapsed < 30.0
