from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.repository import ApplicationRepository


def get_interview_service(db: Session = Depends(get_db)) -> InterviewService:
    notification_service = NotificationService(NotificationRepository(db))
    return InterviewService(
        InterviewRepository(db),
        ApplicationRepository(db),
        notification_service,
    )
