from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_shortlist_persists_candidates_stage_notes_and_profile_completeness(client, hr_token):
    from app.db.session import AsyncSessionLocal
    from app.models.candidate import Candidate, CandidateEducation, CandidateExperience

    async with AsyncSessionLocal() as db:
        candidate = Candidate(
            full_name="Morgan Example",
            email="morgan@example.com",
            phone="555-0100",
            location="Remote",
            summary="Experienced software engineer.",
            technical_skills=["Python", "SQL"],
            soft_skills=[],
            job_titles=["Engineer"],
            years_of_experience=6,
            experience=[],
            projects=[],
            education=[],
            certifications=[],
        )
        db.add(candidate)
        await db.flush()
        db.add(CandidateExperience(candidate_id=candidate.id, title="Engineer", company="Example Co"))
        db.add(CandidateEducation(candidate_id=candidate.id, degree="BSc", institution="Example University"))
        await db.commit()
        candidate_id = candidate.id

    headers = {"Authorization": f"Bearer {hr_token}"}
    created = await client.post(
        "/api/v1/shortlists",
        headers=headers,
        json={"name": "Platform role", "candidate_ids": [candidate_id]},
    )
    assert created.status_code == 200, created.text
    shortlist = created.json()
    assert shortlist["name"] == "Platform role"
    assert shortlist["candidates"][0]["candidate_id"] == candidate_id
    assert shortlist["candidates"][0]["profile_completeness"]["score"] == 85

    updated = await client.patch(
        f"/api/v1/shortlists/{shortlist['id']}/candidates/{candidate_id}",
        headers=headers,
        json={"stage": "interview", "notes": "Strong system design discussion."},
    )
    assert updated.status_code == 200, updated.text
    saved_candidate = updated.json()["candidates"][0]
    assert saved_candidate["stage"] == "interview"
    assert saved_candidate["notes"] == "Strong system design discussion."

    listed = await client.get("/api/v1/shortlists", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == shortlist["id"]
    assert listed.json()[0]["candidates"][0]["notes"] == "Strong system design discussion."

    removed = await client.delete(f"/api/v1/shortlists/{shortlist['id']}/candidates/{candidate_id}", headers=headers)
    assert removed.status_code == 204
    detail = await client.get(f"/api/v1/shortlists/{shortlist['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["candidates"] == []
