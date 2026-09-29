from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.offboarding.repository import OffboardingRepository
from app.modules.offboarding.service import OffboardingService


def build_offboarding_service(db: Session) -> OffboardingService:
    return OffboardingService(
        OffboardingRepository(db),
        EmployeeRepository(db),
    )


def get_offboarding_service(db: Session = Depends(get_db)) -> OffboardingService:
    return build_offboarding_service(db)
