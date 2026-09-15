from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.recipient_user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_unread(self, user_id: int) -> int:
        return (
            self.db.query(Notification)
            .filter(
                Notification.recipient_user_id == user_id,
                Notification.is_read.is_(False),
            )
            .count()
        )

    def get_for_user(self, notification_id: int, user_id: int) -> Notification | None:
        return (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.recipient_user_id == user_id,
            )
            .first()
        )

    def mark_all_as_read(self, user_id: int) -> int:
        now = datetime.now(UTC)
        unread = (
            self.db.query(Notification)
            .filter(
                Notification.recipient_user_id == user_id,
                Notification.is_read.is_(False),
            )
            .all()
        )
        for notification in unread:
            notification.is_read = True
            notification.read_at = now
        if unread:
            self.db.commit()
        return len(unread)

    def save(self, notification: Notification) -> Notification:
        self.db.commit()
        self.db.refresh(notification)
        return notification
