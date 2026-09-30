"""
Password hashing, JWT creation/verification, and OTP generation.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

# Passwords/tokens are hashed with `bcrypt` directly (rather than through
# passlib's CryptContext) to avoid a known passlib<->bcrypt>=4.1 version
# incompatibility during backend auto-detection. bcrypt truncates at 72
# bytes internally; we pre-truncate explicitly so behavior is predictable
# rather than relying on the library's own truncation.
_BCRYPT_MAX_BYTES = 72


def _jwt_secret() -> str:
    if not settings.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY must be configured before using authentication.")
    return settings.JWT_SECRET_KEY


def _prepare(secret: str) -> bytes:
    return secret.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


def _create_token(subject: str, role: str, expires_delta: timedelta, token_type: str, extra: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id, role, timedelta(minutes=settings.JWT_EXPIRE_MINUTES), "access"
    )


def create_refresh_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id, role, timedelta(minutes=settings.JWT_REFRESH_EXPIRE_MINUTES), "refresh"
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError(f"Invalid or expired token: {exc}") from exc


def generate_otp(length: int | None = None) -> str:
    length = length or settings.OTP_LENGTH
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_secure_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Used for storing password-reset/OTP tokens so the DB never holds the raw value."""
    return hash_password(token)


def verify_token_hash(token: str, token_hash: str) -> bool:
    return verify_password(token, token_hash)
