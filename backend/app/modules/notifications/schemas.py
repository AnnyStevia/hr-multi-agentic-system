from datetime import datetime

from pydantic import BaseModel

from app.modules.notifications.models import NotificationType


class NotificationResponse(BaseModel):
    id: int
    type: NotificationType
    title: str
    message: str
    related_entity_type: str | None
    related_entity_id: int | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    updated: int
