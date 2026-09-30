from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    FirstLoginPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyOtpRequest,
)
from app.services import auth_service
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await auth_service.login(db, payload.email, payload.password, ip_address=request.client.host if request.client else None)
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.refresh_access_token(db, payload.refresh_token)
    return TokenResponse(**result)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    account_exists, otp_sent = await auth_service.request_password_reset_otp(db, payload.email)
    if not account_exists:
        message = "This email is not associated with an account in your organization."
    elif not otp_sent:
        message = "This account is inactive. Contact your administrator."
    else:
        message = "A verification code has been sent to your email address."
    return {"account_exists": account_exists, "otp_sent": otp_sent, "message": message}


@router.post("/verify-otp")
async def verify_otp(payload: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    reset_token = await auth_service.verify_password_reset_otp(db, payload.email, payload.otp_code)
    return {"message": "OTP verified.", "reset_token": reset_token}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if payload.reset_token:
        await auth_service.reset_password_with_token(db, payload.email, payload.reset_token, payload.new_password)
    else:
        await auth_service.reset_password_with_otp(db, payload.email, payload.otp_code or "", payload.new_password)
    return {"message": "Password has been reset."}


@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await auth_service.change_password(db, user, payload.current_password, payload.new_password)
    return {"message": "Password changed."}


@router.post("/first-login-password")
async def first_login_password(
    payload: FirstLoginPasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.complete_first_login_password(db, user, payload.new_password)
    return {"message": "Password changed. Continue to your workspace."}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
