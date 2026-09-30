from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.user import AuditLog, Notification


async def create_notification(
    db: AsyncSession, user_id: str, notification_type: NotificationType, title: str, message: str, meta: Optional[dict] = None
) -> Notification:
    notification = Notification(
        user_id=user_id, notification_type=notification_type.value, title=title, message=message, meta=meta or {}
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def list_notifications(db: AsyncSession, user_id: str, unread_only: bool = False, limit: int = 50) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_notifications_read(db: AsyncSession, user_id: str, notification_ids: Optional[list[str]]) -> int:
    stmt = update(Notification).where(Notification.user_id == user_id)
    if notification_ids:
        stmt = stmt.where(Notification.id.in_(notification_ids))
    stmt = stmt.values(is_read=True)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def record_audit_log(
    db: AsyncSession,
    user_id: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict] = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id,
        ip_address=ip_address, details=details or {},
    )
    db.add(entry)
    await db.commit()
    return entry
