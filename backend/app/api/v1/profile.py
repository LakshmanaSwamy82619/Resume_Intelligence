from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UpdateProfileRequest, UserResponse
from app.services.notification_service import record_audit_log

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("", response_model=UserResponse)
async def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("", response_model=UserResponse)
async def update_profile(payload: UpdateProfileRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    changed_fields = [key for key, value in payload.model_dump(exclude_unset=True).items() if value is not None]
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.notification_preferences is not None:
        user.notification_preferences = payload.notification_preferences
    await db.commit()
    if changed_fields:
        await record_audit_log(db, user.id, "profile_updated", resource_type="user", resource_id=user.id, details={"fields": changed_fields})
    await db.refresh(user)
    return user
