from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.modules.employees.models import Department, DepartmentStatus, Employee, EmploymentStatus


class DepartmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, status: DepartmentStatus | None = None) -> list[Department]:
        query = self.db.query(Department)
        if status is not None:
            query = query.filter(Department.status == status)
        return query.order_by(Department.name.asc()).all()

    def get_by_id(self, department_id: int) -> Department | None:
        return self.db.query(Department).filter(Department.id == department_id).first()

    def get_by_name(self, name: str) -> Department | None:
        return self.db.query(Department).filter(Department.name == name).first()

    def add(self, department: Department) -> Department:
        self.db.add(department)
        self.db.commit()
        self.db.refresh(department)
        return department

    def save(self, department: Department) -> Department:
        self.db.commit()
        self.db.refresh(department)
        return department


class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def _query(self):
        return self.db.query(Employee).options(joinedload(Employee.department))

    def list(
        self,
        *,
        status: EmploymentStatus | None,
        department_id: int | None,
        search: str | None,
    ) -> list[Employee]:
        query = self._query()
        if status is not None:
            query = query.filter(Employee.employment_status == status)
        if department_id is not None:
            query = query.filter(Employee.department_id == department_id)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Employee.employee_number.ilike(term),
                    Employee.first_name.ilike(term),
                    Employee.last_name.ilike(term),
                    Employee.email.ilike(term),
                )
            )
        return query.order_by(Employee.employee_number.asc()).all()

    def get_by_id(self, employee_id: int) -> Employee | None:
        return self._query().filter(Employee.id == employee_id).first()

    def get_by_email(self, email: str) -> Employee | None:
        return self.db.query(Employee).filter(Employee.email == email).first()

    def get_by_user_id(self, user_id: int) -> Employee | None:
        return self._query().filter(Employee.user_id == user_id).first()

    def add(self, employee: Employee, *, commit: bool = True) -> Employee:
        if not employee.employee_number or employee.employee_number == "PENDING":
            employee.employee_number = f"TMP-{uuid4().hex[:12]}"
        self.db.add(employee)
        self.db.flush()
        employee.employee_number = f"EMP-{employee.id:06d}"
        if commit:
            self.db.commit()
            return self.get_by_id(employee.id) or employee
        return employee

    def save(self, employee: Employee) -> Employee:
        self.db.commit()
        loaded = self.get_by_id(employee.id)
        return loaded or employee

    def count_active(self) -> int:
        return (
            self.db.query(Employee)
            .filter(Employee.employment_status == EmploymentStatus.ACTIVE)
            .count()
        )
