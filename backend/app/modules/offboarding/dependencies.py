from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.service import AuthService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.offboarding.meeting_service import ExitInterviewMeetingService
from app.modules.offboarding.repository import OffboardingRepository
from app.modules.offboarding.service import OffboardingService
from app.shared.meetings import get_meeting_provider


def build_offboarding_service(db: Session) -> OffboardingService:
    return OffboardingService(
        OffboardingRepository(db),
        EmployeeRepository(db),
        NotificationService(NotificationRepository(db)),
        AuthService(db),
    )


def get_offboarding_service(db: Session = Depends(get_db)) -> OffboardingService:
    return build_offboarding_service(db)


def get_exit_interview_meeting_service(
    db: Session = Depends(get_db),
) -> ExitInterviewMeetingService:
    return ExitInterviewMeetingService(
        OffboardingRepository(db),
        notifications=NotificationService(NotificationRepository(db)),
        provider=get_meeting_provider(),
    )
