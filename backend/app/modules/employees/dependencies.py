from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import DepartmentRepository, EmployeeRepository
from app.modules.employees.service import DepartmentService, EmployeeService


def get_department_service(db: Session = Depends(get_db)) -> DepartmentService:
    return DepartmentService(DepartmentRepository(db))


def get_employee_service(db: Session = Depends(get_db)) -> EmployeeService:
    departments = DepartmentService(DepartmentRepository(db))
    return EmployeeService(EmployeeRepository(db), departments)
