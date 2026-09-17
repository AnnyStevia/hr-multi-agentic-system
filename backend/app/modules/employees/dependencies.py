from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import DepartmentRepository, EmployeeRepository
from app.modules.employees.service import DepartmentService, EmployeeService
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.service import OnboardingService


def get_department_service(db: Session = Depends(get_db)) -> DepartmentService:
    return DepartmentService(DepartmentRepository(db))


def get_employee_service(db: Session = Depends(get_db)) -> EmployeeService:
    departments = DepartmentService(DepartmentRepository(db))
    onboarding = OnboardingService(OnboardingRepository(db), EmployeeRepository(db))
    return EmployeeService(EmployeeRepository(db), departments, onboarding)
