from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_{uuid.uuid4().hex}.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("RERANKER_PROVIDER", "local")
os.environ.setdefault("EMAIL_PROVIDER", "console")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("UPLOAD_DIR", "./data/test_uploads")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "AdminPass123!")

import httpx  # noqa: E402

from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as c:
            yield c


@pytest_asyncio.fixture
async def admin_token(client):
    from app.core.config import get_settings
    from app.core.security import create_access_token
    from app.db.session import AsyncSessionLocal
    from app.models.user import User
    from sqlalchemy import select

    settings = get_settings()
    admin_email = settings.BOOTSTRAP_ADMIN_EMAIL or "admin@example.com"
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(User).where(User.email == admin_email.lower()))).scalar_one_or_none()
    if not admin:
        pytest.skip("Bootstrap admin not configured for this test run (set BOOTSTRAP_ADMIN_EMAIL/PASSWORD).")
    return create_access_token(admin.id, admin.role)


@pytest_asyncio.fixture
async def hr_token(client, admin_token):
    email = f"hr_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/v1/admin/hr-accounts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": email, "full_name": "Test Recruiter", "temporary_password": "HrPass123!"},
    )
    assert r.status_code == 200, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "HrPass123!"})
    assert r.status_code == 200, r.text
    hr_access_token = r.json()["access_token"]
    r = await client.post(
        "/api/v1/auth/first-login-password",
        headers={"Authorization": f"Bearer {hr_access_token}"},
        json={"new_password": "HrPass123!Updated"},
    )
    assert r.status_code == 200, r.text
    return hr_access_token
