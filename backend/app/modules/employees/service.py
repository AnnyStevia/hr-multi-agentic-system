from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.modules.employees.models import (
    Department,
    DepartmentStatus,
    Employee,
    EmploymentStatus,
)
from app.modules.employees.repository import DepartmentRepository, EmployeeRepository
from app.modules.employees.schemas import (
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeUpdateRequest,
)
from app.modules.identity.models import Role, UserRole
from app.modules.recruitment.models import Application
from app.shared.exceptions import AppException

if TYPE_CHECKING:
    from app.modules.onboarding.service import OnboardingService


EMPLOYEE_ROLE_NAME = "employee"


class DepartmentService:
    def __init__(self, repository: DepartmentRepository):
        self.repository = repository

    def list_departments(self, status: str | None = "all") -> list[Department]:
        filter_status = _parse_department_status_filter(status)
        return self.repository.list(filter_status)

    def get_department(self, department_id: int) -> Department:
        department = self.repository.get_by_id(department_id)
        if department is None:
            raise AppException("Department not found", status_code=404)
        return department

    def create_department(self, payload: DepartmentCreateRequest) -> Department:
        name = payload.name.strip()
        if self.repository.get_by_name(name) is not None:
            raise AppException("A department with this name already exists", status_code=409)
        return self.repository.add(Department(name=name, status=DepartmentStatus.ACTIVE))

    def update_department(self, department_id: int, payload: DepartmentUpdateRequest) -> Department:
        department = self.get_department(department_id)
        name = payload.name.strip()
        existing = self.repository.get_by_name(name)
        if existing is not None and existing.id != department.id:
            raise AppException("A department with this name already exists", status_code=409)
        department.name = name
        return self.repository.save(department)

    def deactivate_department(self, department_id: int) -> Department:
        department = self.get_department(department_id)
        department.status = DepartmentStatus.INACTIVE
        return self.repository.save(department)

    def require_active(self, department_id: int) -> Department:
        department = self.repository.get_by_id(department_id)
        if department is None:
            raise AppException("Department not found", status_code=400)
        if department.status != DepartmentStatus.ACTIVE:
            raise AppException("Department is not active", status_code=400)
        return department


class EmployeeService:
    def __init__(
        self,
        employees: EmployeeRepository,
        departments: DepartmentService,
        onboarding: OnboardingService | None = None,
    ):
        self.employees = employees
        self.departments = departments
        self.onboarding = onboarding

    def list_employees(
        self,
        *,
        status: str | None = "active",
        department_id: int | None = None,
        q: str | None = None,
    ) -> tuple[list[Employee], int]:
        rows = self.employees.list(
            status=_parse_employment_status_filter(status),
            department_id=department_id,
            search=q,
        )
        return rows, len(rows)

    def get_employee(self, employee_id: int) -> Employee:
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise AppException("Employee not found", status_code=404)
        return employee

    def create_employee(self, payload: EmployeeCreateRequest) -> Employee:
        self.departments.require_active(payload.department_id)
        email = str(payload.email)
        if self.employees.get_by_email(email) is not None:
            raise AppException("An employee with this email already exists", status_code=409)
        employee = Employee(
            employee_number="PENDING",
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=email,
            phone=_normalize_phone(payload.phone),
            department_id=payload.department_id,
            position=payload.position.strip(),
            hire_date=payload.hire_date,
            employment_status=EmploymentStatus.ACTIVE,
        )
        return self.employees.add(employee)

    def create_from_hired_candidate(self, application: Application, *, commit: bool = True) -> Employee:
        candidate = application.candidate
        user = candidate.user
        job = application.job

        if job.department_id is None:
            raise AppException("Job must have a department before hiring", status_code=400)
        if not candidate.phone or not candidate.phone.strip():
            raise AppException("Candidate phone is required before hiring", status_code=400)

        self.departments.require_active(job.department_id)
        email = user.email
        if self.employees.get_by_email(email) is not None:
            raise AppException("An employee with this email already exists", status_code=409)
        if self.employees.get_by_user_id(user.id) is not None:
            raise AppException("An employee already exists for this user", status_code=409)

        employee = Employee(
            employee_number="PENDING",
            first_name=user.first_name.strip(),
            last_name=user.last_name.strip(),
            email=email,
            phone=_normalize_phone(candidate.phone),
            department_id=job.department_id,
            position=job.title.strip(),
            hire_date=datetime.now(UTC).date(),
            employment_status=EmploymentStatus.ACTIVE,
            user_id=user.id,
        )
        employee = self.employees.add(employee, commit=False)
        if self.onboarding is None:
            raise AppException("Onboarding service is not configured", status_code=500)
        self.onboarding.create_for_employee(employee.id, commit=False)
        _ensure_employee_role(self.employees.db, user.id)
        if commit:
            self.employees.db.commit()
            loaded = self.employees.get_by_id(employee.id)
            return loaded or employee
        return employee

    def get_by_user_id(self, user_id: int) -> Employee | None:
        return self.employees.get_by_user_id(user_id)

    def update_employee(self, employee_id: int, payload: EmployeeUpdateRequest) -> Employee:
        employee = self.get_employee(employee_id)
        data = payload.model_dump(exclude_unset=True)
        if "department_id" in data and data["department_id"] is not None:
            self.departments.require_active(data["department_id"])
        if "email" in data and data["email"] is not None:
            email = str(data["email"])
            existing = self.employees.get_by_email(email)
            if existing is not None and existing.id != employee.id:
                raise AppException("An employee with this email already exists", status_code=409)
            employee.email = email
            data.pop("email")
        if "phone" in data and data["phone"] is not None:
            employee.phone = _normalize_phone(data.pop("phone"))
        for field in ("first_name", "last_name", "position"):
            if field in data and data[field] is not None:
                setattr(employee, field, data[field].strip())
        if "department_id" in data and data["department_id"] is not None:
            employee.department_id = data["department_id"]
        if "hire_date" in data and data["hire_date"] is not None:
            employee.hire_date = data["hire_date"]
        return self.employees.save(employee)

    def deactivate_employee(self, employee_id: int) -> Employee:
        employee = self.get_employee(employee_id)
        employee.employment_status = EmploymentStatus.INACTIVE
        return self.employees.save(employee)

    def count_active(self) -> int:
        return self.employees.count_active()


def build_employee_response(employee: Employee) -> EmployeeResponse:
    return EmployeeResponse(
        id=employee.id,
        employee_number=employee.employee_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        full_name=employee.full_name,
        email=employee.email,
        phone=employee.phone,
        department_id=employee.department_id,
        department=employee.department.name,
        position=employee.position,
        hire_date=employee.hire_date,
        employment_status=employee.employment_status,
        user_id=employee.user_id,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


def _parse_department_status_filter(status: str | None) -> DepartmentStatus | None:
    value = (status or "all").strip().lower()
    if value in {"", "all"}:
        return None
    try:
        return DepartmentStatus(value)
    except ValueError as exc:
        raise AppException("Invalid department status filter", status_code=400) from exc


def _parse_employment_status_filter(status: str | None) -> EmploymentStatus | None:
    value = (status or "active").strip().lower()
    if value == "all":
        return None
    try:
        return EmploymentStatus(value)
    except ValueError as exc:
        raise AppException("Invalid employment status filter", status_code=400) from exc


def _normalize_phone(value: str) -> str:
    stripped = value.strip()
    digits = "".join(character for character in stripped if character.isdigit())
    if len(digits) < 8 or len(stripped) > 30:
        raise AppException("Enter a valid phone number", status_code=400)
    allowed = set("0123456789+ -().")
    if any(character not in allowed for character in stripped):
        raise AppException("Enter a valid phone number", status_code=400)
    return stripped


def _ensure_employee_role(db, user_id: int) -> None:
    employee_role = db.query(Role).filter(Role.name == EMPLOYEE_ROLE_NAME).first()
    if employee_role is None:
        raise AppException("Employee role is not configured", status_code=500)
    existing = (
        db.query(UserRole)
        .filter(UserRole.user_id == user_id, UserRole.role_id == employee_role.id)
        .first()
    )
    if existing is None:
        db.add(UserRole(user_id=user_id, role_id=employee_role.id))
