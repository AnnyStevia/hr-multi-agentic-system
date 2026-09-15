from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import DepartmentRepository
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.repository import JobRepository
from app.modules.recruitment.service import JobService
from app.shared.storage import StorageService, get_storage_service


def get_job_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(JobRepository(db), DepartmentRepository(db))


def get_application_service(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> ApplicationService:
    notification_service = NotificationService(NotificationRepository(db))
    return ApplicationService(db, storage, notification_service)
