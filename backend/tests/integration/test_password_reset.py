from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import OTPVerification, User

pytestmark = pytest.mark.asyncio


async def _new_user() -> tuple[str, str]:
    email = f"password-reset-{uuid.uuid4().hex}@example.com"
    password = "InitialPass123!"
    async with AsyncSessionLocal() as db:
        db.add(User(email=email, hashed_password=hash_password(password), full_name="Reset Test", role="hr", is_active=True))
        await db.commit()
    return email, password


async def _request_otp(client, monkeypatch) -> tuple[str, str]:
    email, _ = await _new_user()
    captured = []

    from app.services import auth_service

    monkeypatch.setattr(auth_service, "send_email", lambda _to, _subject, body: captured.append(body) or True)
    response = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert response.status_code == 200, response.text
    match = re.search(r"code for password reset is: (\d+)", captured[-1])
    assert match, "The test mail capture did not contain a reset OTP."
    return email, match.group(1)


def _wrong_otp(otp: str = "000000") -> str:
    return otp[:-1] + str((int(otp[-1]) + 1) % 10)


async def test_forgot_password_reports_registered_active_account(client, monkeypatch):
    email, _ = await _new_user()
    from app.services import auth_service

    monkeypatch.setattr(auth_service, "send_email", lambda *_args: True)
    response = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert response.status_code == 200, response.text
    assert response.json()["account_exists"] is True
    assert response.json()["otp_sent"] is True


async def test_forgot_password_reports_unregistered_email(client, monkeypatch):
    from app.services import auth_service

    monkeypatch.setattr(auth_service, "send_email", lambda *_args: pytest.fail("No OTP should be sent."))
    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": f"missing-{uuid.uuid4().hex}@example.com"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["account_exists"] is False
    assert response.json()["otp_sent"] is False


async def test_two_step_password_reset_accepts_reset_token(client, monkeypatch):
    email, old_password = await _new_user()
    captured = []

    from app.services import auth_service

    monkeypatch.setattr(auth_service, "send_email", lambda _to, _subject, body: captured.append(body) or True)
    assert (await client.post("/api/v1/auth/forgot-password", json={"email": email})).status_code == 200
    otp = re.search(r"code for password reset is: (\d+)", captured[-1]).group(1)

    verified = await client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp})
    assert verified.status_code == 200, verified.text
    reset_token = verified.json()["reset_token"]
    changed = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "reset_token": reset_token, "new_password": "ReplacementPass123!"},
    )
    assert changed.status_code == 200, changed.text
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": old_password})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": "ReplacementPass123!"})).status_code == 200


async def test_invalid_otp_is_rejected(client, monkeypatch):
    email, otp = await _request_otp(client, monkeypatch)
    response = await client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": _wrong_otp(otp)})
    assert response.status_code == 401


async def test_expired_otp_is_rejected(client, monkeypatch):
    email, otp = await _request_otp(client, monkeypatch)
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        row = (await db.execute(select(OTPVerification).where(OTPVerification.user_id == user.id, OTPVerification.purpose == "password_reset"))).scalars().first()
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        await db.commit()
    response = await client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp})
    assert response.status_code == 401


async def test_otp_cannot_be_reused_after_verification(client, monkeypatch):
    email, otp = await _request_otp(client, monkeypatch)
    first = await client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp})
    assert first.status_code == 200
    second = await client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp})
    assert second.status_code == 401


async def test_disabled_user_cannot_verify_password_reset_otp(client, monkeypatch):
    email, otp = await _request_otp(client, monkeypatch)
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.is_active = False
        await db.commit()
    response = await client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp})
    assert response.status_code == 401


async def test_repeated_invalid_otp_attempts_remain_rejected(client, monkeypatch):
    email, otp = await _request_otp(client, monkeypatch)
    for _ in range(6):
        response = await client.post("/api/v1/auth/verify-otp", json={"email": email, "otp_code": _wrong_otp(otp)})
        assert response.status_code == 401
