from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import DepartmentRepository, EmployeeRepository
from app.modules.employees.service import DepartmentService, EmployeeService
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.dependencies import build_onboarding_service
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.repository import ApplicationRepository
from app.shared.storage import StorageService, get_storage_service


def get_interview_service(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> InterviewService:
    notification_service = NotificationService(NotificationRepository(db))
    department_service = DepartmentService(DepartmentRepository(db))
    onboarding_service = build_onboarding_service(db, storage)
    employee_service = EmployeeService(
        EmployeeRepository(db), department_service, onboarding_service
    )
    application_service = ApplicationService(db, storage, notification_service)
    return InterviewService(
        InterviewRepository(db),
        ApplicationRepository(db),
        notification_service,
        employee_service,
        application_service,
    )
