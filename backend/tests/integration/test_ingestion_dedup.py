from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_duplicate_file_upload_returns_existing_resume(client, hr_token):
    content = b"Jordan Example\njordan@example.com\nSkills\nPython and SQL"
    headers = {"Authorization": f"Bearer {hr_token}"}
    first = await client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("jordan.txt", content, "text/plain")},
    )
    assert first.status_code == 200, first.text
    second = await client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("jordan-copy.txt", content, "text/plain")},
    )
    assert second.status_code == 200, second.text
    assert first.json()["is_duplicate"] is False
    assert second.json()["is_duplicate"] is True
    assert second.json()["resume_id"] == first.json()["resume_id"]
