from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.offboarding.dependencies import build_offboarding_service
from app.modules.offboarding.repository import OffboardingRepository
from app.modules.offboarding_requests.repository import OffboardingRequestRepository
from app.modules.offboarding_requests.service import OffboardingRequestService


def get_offboarding_request_service(
    db: Session = Depends(get_db),
) -> OffboardingRequestService:
    return OffboardingRequestService(
        OffboardingRequestRepository(db),
        EmployeeRepository(db),
        OffboardingRepository(db),
        NotificationService(NotificationRepository(db)),
        build_offboarding_service(db),
    )
