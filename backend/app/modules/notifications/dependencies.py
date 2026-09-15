from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(NotificationRepository(db))
