from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, RateLimitedError, UnauthorizedError, ValidationAppError
from app.core.email_validation import suggest_email_correction
from app.core.password_policy import enforce_password_policy
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
    verify_token_hash,
)
from app.models.enums import NotificationType, UserRole
from app.models.user import OTPVerification, PasswordResetToken, User
from app.services.email_service import (
    account_created_email_body,
    otp_email_body,
    password_reset_confirmation_body,
    send_email,
)
from app.services.notification_service import create_notification, record_audit_log
from app.utils.rate_limit import is_rate_limited

settings = get_settings()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def login(db: AsyncSession, email: str, password: str, ip_address: str | None = None) -> dict:
    if is_rate_limited(f"login:{email.lower()}", settings.RATE_LIMIT_LOGIN_PER_MINUTE, 60):
        raise RateLimitedError("Too many login attempts. Please try again shortly.")

    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        await record_audit_log(db, None, "login_failed", details={"email": email})
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("This account has been disabled. Contact your administrator.")

    user.last_login_at = datetime.utcnow()
    await db.commit()

    access = create_access_token(user.id, user.role)
    refresh = create_refresh_token(user.id, user.role)
    await record_audit_log(db, user.id, "login", resource_type="user", resource_id=user.id, ip_address=ip_address)

    return {
        "access_token": access,
        "refresh_token": refresh,
        "role": user.role,
        "user_id": user.id,
        "must_change_password": user.must_change_password,
    }


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise UnauthorizedError(str(exc))

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Not a refresh token.")

    user = await get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or disabled.")

    access = create_access_token(user.id, user.role)
    new_refresh = create_refresh_token(user.id, user.role)
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "role": user.role,
        "user_id": user.id,
        "must_change_password": user.must_change_password,
    }


async def create_hr_account(db: AsyncSession, admin_id: str, email: str, full_name: str, phone: str | None, temporary_password: str | None) -> User:
    suggested_email = suggest_email_correction(email)
    if suggested_email:
        raise ValidationAppError(f"Check the email domain. Did you mean {suggested_email}?")
    existing = await get_user_by_email(db, email)
    if existing:
        raise ConflictError("A user with this email already exists.")

    temp_password = temporary_password or generate_secure_token(9)
    user = User(
        email=email.lower(),
        hashed_password=hash_password(temp_password),
        full_name=full_name,
        phone=phone,
        role=UserRole.HR.value,
        is_active=True,
        must_change_password=True,
        created_by_admin_id=admin_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    send_email(
        user.email,
        "Welcome to Resume Intelligence - your HR account is ready",
        account_created_email_body(full_name, user.email, temp_password),
    )
    await create_notification(
        db, user.id, NotificationType.ACCOUNT_CREATED, "Account created",
        "Your HR account has been created. Check your email for login details.",
    )
    await record_audit_log(db, admin_id, "create_hr_account", resource_type="user", resource_id=user.id)
    return user


async def set_account_active(db: AsyncSession, admin_id: str, target_user_id: str, is_active: bool) -> User:
    user = await get_user_by_id(db, target_user_id)
    if not user:
        raise ValidationAppError("User not found.")
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    await record_audit_log(
        db, admin_id, "set_account_active", resource_type="user", resource_id=user.id, details={"is_active": is_active}
    )
    return user


async def request_password_reset_otp(db: AsyncSession, email: str) -> tuple[bool, bool]:
    if is_rate_limited(f"otp:{email.lower()}", settings.RATE_LIMIT_OTP_PER_MINUTE, 60):
        raise RateLimitedError("Too many OTP requests. Please try again shortly.")

    user = await get_user_by_email(db, email)
    if not user:
        return False, False
    if not user.is_active:
        return True, False

    code = generate_otp()
    otp = OTPVerification(
        user_id=user.id,
        purpose="password_reset",
        code_hash=hash_token(code),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    await db.commit()

    send_email(user.email, "Your verification code", otp_email_body(user.full_name, code, "password_reset"))
    return True, True


async def verify_password_reset_otp(db: AsyncSession, email: str, otp_code: str) -> str:
    """Returns a short-lived reset token to be used with reset_password."""
    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        raise UnauthorizedError("Invalid verification code.")

    result = await db.execute(
        select(OTPVerification)
        .where(OTPVerification.user_id == user.id, OTPVerification.purpose == "password_reset", OTPVerification.consumed_at.is_(None))
        .order_by(OTPVerification.created_at.desc())
    )
    otp = result.scalars().first()
    if not otp or otp.expires_at < datetime.utcnow():
        raise UnauthorizedError("Invalid or expired verification code.")

    otp.attempt_count += 1
    if otp.attempt_count > 5:
        raise UnauthorizedError("Too many incorrect attempts. Request a new code.")

    if not verify_token_hash(otp_code, otp.code_hash):
        await db.commit()
        raise UnauthorizedError("Invalid verification code.")

    otp.consumed_at = datetime.utcnow()

    reset_token = generate_secure_token()
    reset_record = PasswordResetToken(
        user_id=user.id, token_hash=hash_token(reset_token), expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db.add(reset_record)
    await db.commit()
    return reset_token


async def reset_password_with_token(db: AsyncSession, email: str, reset_token: str, new_password: str) -> None:
    """Complete the second step using the short-lived token returned by OTP verification."""
    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        raise UnauthorizedError("Invalid or expired password reset session.")
    result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .order_by(PasswordResetToken.created_at.desc())
    )
    record = result.scalars().first()
    if not record or record.expires_at < datetime.utcnow() or not verify_token_hash(reset_token, record.token_hash):
        raise UnauthorizedError("Invalid or expired password reset session.")

    user.hashed_password = hash_password(new_password)
    record.used_at = datetime.utcnow()
    await db.commit()
    send_email(user.email, "Your password was changed", password_reset_confirmation_body(user.full_name))
    await create_notification(db, user.id, NotificationType.SECURITY_EVENT, "Password changed", "Your password was just reset.")
    await record_audit_log(db, user.id, "password_reset")


async def reset_password_with_otp(db: AsyncSession, email: str, otp_code: str, new_password: str) -> None:
    """Convenience one-shot flow: verify OTP and reset the password together."""
    reset_token = await verify_password_reset_otp(db, email, otp_code)
    await reset_password_with_token(db, email, reset_token, new_password)


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise UnauthorizedError("Current password is incorrect.")
    user.hashed_password = hash_password(new_password)
    await db.commit()
    send_email(user.email, "Your password was changed", password_reset_confirmation_body(user.full_name))
    await create_notification(db, user.id, NotificationType.SECURITY_EVENT, "Password changed", "Your password was just changed.")
    await record_audit_log(db, user.id, "change_password")


async def complete_first_login_password(db: AsyncSession, user: User, new_password: str) -> None:
    if user.role != UserRole.HR.value or not user.must_change_password:
        raise ValidationAppError("This account does not require a first-login password change.")
    enforce_password_policy(new_password)
    if verify_password(new_password, user.hashed_password):
        raise ValidationAppError("Choose a password different from your temporary password.")
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    await db.commit()
    send_email(user.email, "Your password was changed", password_reset_confirmation_body(user.full_name))
    await create_notification(db, user.id, NotificationType.SECURITY_EVENT, "Password changed", "Your first-login password was changed.")
    await record_audit_log(db, user.id, "first_login_password_changed")
