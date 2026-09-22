from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import (
    DepartmentRepository,
    EmployeeRepository,
    PositionRepository,
)
from app.modules.employees.service import DepartmentService, EmployeeService, PositionService
from app.modules.onboarding.dependencies import build_onboarding_service


def get_department_service(db: Session = Depends(get_db)) -> DepartmentService:
    return DepartmentService(DepartmentRepository(db))


def get_position_service(db: Session = Depends(get_db)) -> PositionService:
    return PositionService(PositionRepository(db), DepartmentService(DepartmentRepository(db)))


def get_employee_service(db: Session = Depends(get_db)) -> EmployeeService:
    departments = DepartmentService(DepartmentRepository(db))
    positions = PositionService(PositionRepository(db), departments)
    onboarding = build_onboarding_service(db)
    return EmployeeService(EmployeeRepository(db), departments, onboarding, positions)
