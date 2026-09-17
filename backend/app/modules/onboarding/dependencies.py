from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.dependencies import require_roles
from app.modules.identity.models import User
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.service import OnboardingService


def get_onboarding_service(db: Session = Depends(get_db)) -> OnboardingService:
    return OnboardingService(
        OnboardingRepository(db),
        EmployeeRepository(db),
        NotificationService(NotificationRepository(db)),
    )


def require_careers_access(
    current_user: User = Depends(require_roles("candidate")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> User:
    roles = {user_role.role.name for user_role in current_user.user_roles}
    if "employee" in roles and onboarding_service.get_active_onboarding_for_user(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete onboarding before accessing careers",
        )
    return current_user


def require_employee_access_cleared(
    current_user: User = Depends(require_roles("employee")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> User:
    if onboarding_service.get_active_onboarding_for_user(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete onboarding before accessing this resource",
        )
    return current_user
