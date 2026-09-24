from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.service import DocumentService
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.dependencies import require_roles
from app.modules.identity.models import User
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.service import OnboardingService
from app.modules.onboarding.verification import OnboardingTaskVerificationService
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.service import ProfileService
from app.modules.training.repository import TrainingRepository
from app.shared.storage import StorageService, get_storage_service


def build_onboarding_service(
    db: Session,
    storage: StorageService | None = None,
) -> OnboardingService:
    employees = EmployeeRepository(db)
    documents_repo = DocumentRepository(db)
    trainings = TrainingRepository(db)
    profile = ProfileService(ProfileRepository(db), employees, storage) if storage else None
    documents = DocumentService(documents_repo, employees, storage) if storage else None
    # When storage is unavailable (sync helper may pass None), still build document checks via repo
    if documents is None:
        documents = DocumentService(documents_repo, employees, _NullStorage())
    if profile is None:
        profile = ProfileService(ProfileRepository(db), employees, _NullStorage())

    verification = OnboardingTaskVerificationService(
        profile=profile,
        documents=documents,
        trainings=trainings,
    )
    return OnboardingService(
        OnboardingRepository(db),
        employees,
        NotificationService(NotificationRepository(db)),
        documents_repo,
        trainings,
        verification,
    )


class _NullStorage:
    """Placeholder storage for verification-only Document/Profile construction."""

    def upload_file(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("Storage is not available in this context")

    def delete_file(self, *args, **kwargs):  # pragma: no cover
        pass

    def generate_presigned_url(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("Storage is not available in this context")

    def download_file(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("Storage is not available in this context")

    def get_file_metadata(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("Storage is not available in this context")

    def check_connectivity(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("Storage is not available in this context")


def get_onboarding_service(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> OnboardingService:
    return build_onboarding_service(db, storage)


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
