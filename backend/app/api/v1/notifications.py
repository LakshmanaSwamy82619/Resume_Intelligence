from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import MarkNotificationReadRequest, NotificationResponse
from app.services.notification_service import list_notifications, mark_notifications_read, record_audit_log

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def get_notifications(unread_only: bool = False, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await list_notifications(db, user.id, unread_only=unread_only)


@router.post("/mark-read")
async def mark_read(payload: MarkNotificationReadRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await mark_notifications_read(db, user.id, payload.notification_ids)
    if count:
        await record_audit_log(db, user.id, "notifications_marked_read", resource_type="notification", details={"count": count})
    return {"marked_read": count}
