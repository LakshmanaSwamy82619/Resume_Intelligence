from __future__ import annotations

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import get_user_by_id


async def get_current_user(
    request: Request, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise UnauthorizedError(str(exc))

    if payload.get("type") != "access":
        raise UnauthorizedError("Not an access token.")

    user = await get_user_by_id(db, payload["sub"])
    if not user:
        raise UnauthorizedError("User not found.")
    if not user.is_active:
        raise UnauthorizedError("This account has been disabled.")
    if user.role == UserRole.HR.value and user.must_change_password:
        allowed = {
            ("GET", "/api/v1/auth/me"),
            ("POST", "/api/v1/auth/first-login-password"),
        }
        if (request.method, request.url.path) not in allowed:
            raise ForbiddenError(
                "Change your temporary password before accessing the HR workspace.",
                error_code="password_change_required",
            )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise ForbiddenError("Administrator access required.")
    return user


async def require_hr(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.HR.value:
        raise ForbiddenError("HR access required.")
    return user
