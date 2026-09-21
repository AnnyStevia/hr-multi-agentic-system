from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import (
    DepartmentRepository,
    EmployeeRepository,
    PositionRepository,
)
from app.modules.employees.service import DepartmentService, EmployeeService, PositionService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.service import OnboardingService


def get_department_service(db: Session = Depends(get_db)) -> DepartmentService:
    return DepartmentService(DepartmentRepository(db))


def get_position_service(db: Session = Depends(get_db)) -> PositionService:
    return PositionService(PositionRepository(db), DepartmentService(DepartmentRepository(db)))


def get_employee_service(db: Session = Depends(get_db)) -> EmployeeService:
    departments = DepartmentService(DepartmentRepository(db))
    positions = PositionService(PositionRepository(db), departments)
    onboarding = OnboardingService(
        OnboardingRepository(db),
        EmployeeRepository(db),
        NotificationService(NotificationRepository(db)),
    )
    return EmployeeService(EmployeeRepository(db), departments, onboarding, positions)
