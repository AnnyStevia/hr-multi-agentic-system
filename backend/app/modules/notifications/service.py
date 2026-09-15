from datetime import UTC, datetime

from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import NotificationResponse
from app.shared.exceptions import AppException


class NotificationService:
    def __init__(self, repository: NotificationRepository):
        self.repository = repository

    def create_notification(
        self,
        *,
        recipient_user_id: int,
        type: NotificationType,
        title: str,
        message: str,
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            recipient_user_id=recipient_user_id,
            type=type,
            title=title.strip(),
            message=message.strip(),
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            is_read=False,
        )
        return self.repository.add(notification)

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[Notification]:
        return self.repository.list_for_user(user_id, limit=limit)

    def get_unread_count(self, user_id: int) -> int:
        return self.repository.count_unread(user_id)

    def mark_as_read(self, notification_id: int, user_id: int) -> Notification:
        notification = self.repository.get_for_user(notification_id, user_id)
        if notification is None:
            raise AppException("Notification not found", status_code=404)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            return self.repository.save(notification)
        return notification

    def mark_all_as_read(self, user_id: int) -> int:
        return self.repository.mark_all_as_read(user_id)

    def exists_for_entity(
        self,
        *,
        recipient_user_id: int,
        type: NotificationType,
        related_entity_type: str,
        related_entity_id: int,
    ) -> bool:
        return self.repository.exists_for_entity(
            recipient_user_id=recipient_user_id,
            type=type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

    def create_if_absent(
        self,
        *,
        recipient_user_id: int,
        type: NotificationType,
        title: str,
        message: str,
        related_entity_type: str,
        related_entity_id: int,
    ) -> Notification | None:
        if self.exists_for_entity(
            recipient_user_id=recipient_user_id,
            type=type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        ):
            return None
        return self.create_notification(
            recipient_user_id=recipient_user_id,
            type=type,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )


def build_notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
        is_read=notification.is_read,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )
