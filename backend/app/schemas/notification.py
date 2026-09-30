from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    message: str
    is_read: bool
    meta: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarkNotificationReadRequest(BaseModel):
    notification_ids: Optional[list[str]] = None  # None => mark all as read
