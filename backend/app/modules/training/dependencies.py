from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.training.repository import TrainingRepository
from app.modules.training.service import TrainingService


def get_training_service(db: Session = Depends(get_db)) -> TrainingService:
    return TrainingService(
        TrainingRepository(db),
        OnboardingRepository(db),
        EmployeeRepository(db),
        NotificationService(NotificationRepository(db)),
    )
