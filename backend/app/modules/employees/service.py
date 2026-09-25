from __future__ import annotations

import calendar
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from app.modules.employees.models import (
    Department,
    DepartmentStatus,
    Employee,
    EmploymentStatus,
    Position,
)
from app.modules.employees.repository import (
    DepartmentRepository,
    EmployeeRepository,
    PositionRepository,
)
from app.modules.employees.schemas import (
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    DirectoryEntry,
    DirectoryResponse,
    EmployeeCreateRequest,
    EmployeeOrganizationResponse,
    EmployeeResponse,
    EmployeeUpdateRequest,
    HierarchyNode,
    HierarchyResponse,
    OrgPersonSummary,
    PositionCreateRequest,
    PositionResponse,
    PositionUpdateRequest,
    DepartmentResponse,
)
from app.modules.identity.models import Role, UserRole
from app.modules.leave.schemas import CurrentWorkStatus
from app.modules.leave.status import derive_current_work_status
from sqlalchemy.orm import object_session
from app.modules.recruitment.models import Application, EmploymentType
from app.shared.exceptions import AppException

if TYPE_CHECKING:
    from app.modules.onboarding.service import OnboardingService
    from app.shared.storage.base import StorageService


EMPLOYEE_ROLE_NAME = "employee"
PRESIGNED_URL_EXPIRES_IN = 300


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


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


class PositionService:
    def __init__(self, repository: PositionRepository, departments: DepartmentService):
        self.repository = repository
        self.departments = departments

    def list_positions(
        self, *, department_id: int | None = None, q: str | None = None
    ) -> list[Position]:
        return self.repository.list(department_id=department_id, q=q)

    def get_position(self, position_id: int) -> Position:
        position = self.repository.get_by_id(position_id)
        if position is None:
            raise AppException("Position not found", status_code=404)
        return position

    def create_position(self, payload: PositionCreateRequest) -> Position:
        title = payload.title.strip()
        if not title:
            raise AppException("Position title is required", status_code=400)
        if self.repository.get_by_title(title) is not None:
            raise AppException("A position with this title already exists", status_code=409)
        department_id = payload.department_id
        if department_id is not None:
            self.departments.require_active(department_id)
        description = payload.description.strip() if payload.description else None
        return self.repository.add(
            Position(title=title, description=description or None, department_id=department_id)
        )

    def update_position(self, position_id: int, payload: PositionUpdateRequest) -> Position:
        position = self.get_position(position_id)
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            title = data["title"].strip()
            if not title:
                raise AppException("Position title is required", status_code=400)
            existing = self.repository.get_by_title(title)
            if existing is not None and existing.id != position.id:
                raise AppException("A position with this title already exists", status_code=409)
            position.title = title
        if "description" in data:
            value = data["description"]
            position.description = value.strip() if isinstance(value, str) and value.strip() else None
        if "department_id" in data:
            department_id = data["department_id"]
            if department_id is not None:
                self.departments.require_active(department_id)
            position.department_id = department_id
        return self.repository.save(position)

    def delete_position(self, position_id: int) -> None:
        position = self.get_position(position_id)
        if self.repository.count_employees(position_id) > 0:
            raise AppException(
                "Cannot delete a position that is still assigned to employees",
                status_code=409,
            )
        self.repository.delete(position)

    def get_or_create_by_title(
        self, title: str, *, department_id: int | None = None, commit: bool = True
    ) -> Position:
        clean = title.strip()
        existing = self.repository.get_by_title(clean)
        if existing is not None:
            return existing
        position = Position(title=clean, description=None, department_id=department_id)
        self.repository.db.add(position)
        self.repository.db.flush()
        if commit:
            self.repository.db.commit()
            loaded = self.repository.get_by_id(position.id)
            return loaded or position
        return position


class EmployeeService:
    def __init__(
        self,
        employees: EmployeeRepository,
        departments: DepartmentService,
        onboarding: OnboardingService | None = None,
        positions: PositionService | None = None,
    ):
        self.employees = employees
        self.departments = departments
        self.onboarding = onboarding
        self.positions = positions

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

        position_id, position_title = self._resolve_position_fields(
            position_id=payload.position_id,
            position_title=payload.position,
            department_id=payload.department_id,
        )
        if payload.manager_id is not None:
            self._validate_manager(None, payload.manager_id)

        employee = Employee(
            employee_number="PENDING",
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=email,
            phone=_normalize_phone(payload.phone),
            department_id=payload.department_id,
            position=position_title,
            position_id=position_id,
            manager_id=payload.manager_id,
            hire_date=payload.hire_date,
            employment_type=payload.employment_type or EmploymentType.FULL_TIME,
            employment_end_date=(
                payload.employment_end_date
                if payload.employment_type == EmploymentType.INTERNSHIP
                else None
            ),
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

        title = job.title.strip()
        position_id = None
        if self.positions is not None:
            position = self.positions.get_or_create_by_title(
                title, department_id=job.department_id, commit=False
            )
            position_id = position.id

        hire_date = datetime.now(UTC).date()
        employment_type = job.employment_type or EmploymentType.FULL_TIME
        employment_end_date = None
        if employment_type == EmploymentType.INTERNSHIP:
            if job.internship_duration_months is None:
                raise AppException(
                    "Job internship duration is required before hiring an intern",
                    status_code=400,
                )
            employment_end_date = add_months(hire_date, job.internship_duration_months)

        employee = Employee(
            employee_number="PENDING",
            first_name=user.first_name.strip(),
            last_name=user.last_name.strip(),
            email=email,
            phone=_normalize_phone(candidate.phone),
            department_id=job.department_id,
            position=title,
            position_id=position_id,
            hire_date=hire_date,
            employment_type=employment_type,
            employment_end_date=employment_end_date,
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
            if loaded is not None:
                self.onboarding.notify_onboarding_started(loaded)
                return loaded
            return employee
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
        for field in ("first_name", "last_name"):
            if field in data and data[field] is not None:
                setattr(employee, field, data[field].strip())
        if "department_id" in data and data["department_id"] is not None:
            employee.department_id = data["department_id"]
        if "hire_date" in data and data["hire_date"] is not None:
            employee.hire_date = data["hire_date"]
        if "employment_type" in data and data["employment_type"] is not None:
            employee.employment_type = data["employment_type"]
        if "employment_end_date" in data:
            employee.employment_end_date = data["employment_end_date"]

        if employee.employment_type == EmploymentType.INTERNSHIP:
            if employee.employment_end_date is None:
                raise AppException(
                    "employment_end_date is required for internship employees",
                    status_code=400,
                )
            if employee.employment_end_date < employee.hire_date:
                raise AppException(
                    "employment_end_date must be on or after hire_date",
                    status_code=400,
                )
        else:
            employee.employment_end_date = None

        touching_position = "position_id" in data or "position" in data
        if touching_position:
            if "position_id" in data and data["position_id"] is not None:
                pos = self._require_positions().get_position(data["position_id"])
                employee.position_id = pos.id
                employee.position = pos.title
            elif "position" in data and data["position"] is not None:
                title = data["position"].strip()
                pos = self._require_positions().get_or_create_by_title(
                    title, department_id=employee.department_id
                )
                employee.position_id = pos.id
                employee.position = pos.title
            elif "position_id" in data and data["position_id"] is None:
                raise AppException("position_id cannot be cleared", status_code=400)

        if "manager_id" in data:
            self._validate_manager(
                employee.id,
                data["manager_id"],
                current_manager_id=employee.manager_id,
            )
            employee.manager_id = data["manager_id"]

        return self.employees.save(employee)

    def convert_intern_to_employee(
        self, employee_id: int, actor_user_id: int
    ) -> Employee:
        del actor_user_id  # reserved for future audit; auth is at API layer
        employee = self.get_employee(employee_id)
        if employee.employment_type == EmploymentType.FULL_TIME:
            return employee
        if employee.employment_type != EmploymentType.INTERNSHIP:
            raise AppException(
                "Only internship employees can be converted to full-time",
                status_code=400,
            )
        employee.employment_type = EmploymentType.FULL_TIME
        employee.employment_end_date = None
        return self.employees.save(employee)

    def deactivate_employee(self, employee_id: int) -> Employee:
        employee = self.get_employee(employee_id)
        employee.employment_status = EmploymentStatus.INACTIVE
        return self.employees.save(employee)

    def count_active(self) -> int:
        return self.employees.count_active()

    def get_organization(self, employee_id: int) -> EmployeeOrganizationResponse:
        employee = self.get_employee(employee_id)
        return build_organization_response(employee)

    def get_hierarchy(self) -> HierarchyResponse:
        employees = self.employees.list_for_organization()
        by_manager: dict[int | None, list[Employee]] = {}
        for employee in employees:
            by_manager.setdefault(employee.manager_id, []).append(employee)

        def build_node(employee: Employee) -> HierarchyNode:
            children = [
                build_node(child)
                for child in sorted(
                    by_manager.get(employee.id, []),
                    key=lambda item: (item.last_name.lower(), item.first_name.lower()),
                )
            ]
            return HierarchyNode(
                employee_id=employee.id,
                name=employee.full_name,
                position=_display_position(employee),
                department=employee.department.name if employee.department else None,
                children=children,
            )

        roots = sorted(
            by_manager.get(None, []),
            key=lambda item: (item.last_name.lower(), item.first_name.lower()),
        )
        # Orphans whose manager is inactive/missing still appear as roots
        known_ids = {employee.id for employee in employees}
        for employee in employees:
            if employee.manager_id is not None and employee.manager_id not in known_ids:
                roots.append(employee)
        roots = sorted(
            {employee.id: employee for employee in roots}.values(),
            key=lambda item: (item.last_name.lower(), item.first_name.lower()),
        )
        return HierarchyResponse(employees=[build_node(root) for root in roots])

    def get_directory(
        self, *, q: str | None = None, storage: StorageService | None = None
    ) -> DirectoryResponse:
        employees = self.employees.list_for_organization(search=q)
        items: list[DirectoryEntry] = []
        for employee in employees:
            picture_url = None
            has_picture = bool(employee.profile_picture_storage_key)
            if has_picture and storage is not None and employee.profile_picture_storage_key:
                try:
                    picture_url = storage.generate_presigned_url(
                        employee.profile_picture_storage_key,
                        expires_in=PRESIGNED_URL_EXPIRES_IN,
                    )
                except Exception:
                    picture_url = None
            items.append(
                DirectoryEntry(
                    employee_id=employee.id,
                    full_name=employee.full_name,
                    position=_display_position(employee),
                    department=employee.department.name if employee.department else None,
                    manager=employee.manager.full_name if employee.manager else None,
                    has_profile_picture=has_picture,
                    profile_picture_url=picture_url,
                )
            )
        return DirectoryResponse(items=items, total=len(items))

    def _require_positions(self) -> PositionService:
        if self.positions is None:
            raise AppException("Position service is not configured", status_code=500)
        return self.positions

    def _resolve_position_fields(
        self,
        *,
        position_id: int | None,
        position_title: str | None,
        department_id: int | None,
        prefer_existing_id: bool = False,
        existing_id: int | None = None,
        existing_title: str | None = None,
    ) -> tuple[int | None, str]:
        positions = self._require_positions()
        if position_id is not None:
            position = positions.get_position(position_id)
            return position.id, position.title
        if position_title and position_title.strip():
            position = positions.get_or_create_by_title(
                position_title, department_id=department_id
            )
            return position.id, position.title
        if prefer_existing_id and existing_id is not None:
            position = positions.get_position(existing_id)
            return position.id, position.title
        if existing_title and existing_title.strip():
            position = positions.get_or_create_by_title(
                existing_title, department_id=department_id
            )
            return position.id, position.title
        raise AppException("Position is required", status_code=400)

    def _validate_manager(
        self,
        employee_id: int | None,
        manager_id: int | None,
        *,
        current_manager_id: int | None = None,
    ) -> None:
        validate_manager_assignment(
            self.employees,
            employee_id=employee_id,
            manager_id=manager_id,
            current_manager_id=current_manager_id,
        )


def validate_manager_assignment(
    employees: EmployeeRepository,
    *,
    employee_id: int | None,
    manager_id: int | None,
    current_manager_id: int | None = None,
) -> None:
    """Validate a new or updated manager_id assignment.

    Existing non-ACTIVE managers may be kept when manager_id is unchanged
    (historical relationships). New assignments require an ACTIVE manager.
    """
    if manager_id is None:
        return
    if employee_id is not None and manager_id == employee_id:
        raise AppException("An employee cannot report to themselves", status_code=400)
    manager = employees.get_by_id(manager_id)
    if manager is None:
        raise AppException("Manager not found", status_code=404)
    if (
        manager.employment_status != EmploymentStatus.ACTIVE
        and manager_id != current_manager_id
    ):
        raise AppException("Manager must be an active employee", status_code=400)
    if employee_id is None:
        return
    # Walk up from proposed manager; if we hit employee_id, cycle
    seen: set[int] = set()
    current_id: int | None = manager_id
    while current_id is not None:
        if current_id == employee_id:
            raise AppException(
                "Circular reporting relationship is not allowed",
                status_code=400,
            )
        if current_id in seen:
            break
        seen.add(current_id)
        current = employees.get_by_id(current_id)
        if current is None:
            break
        current_id = current.manager_id


def build_employee_response(employee: Employee) -> EmployeeResponse:
    session = object_session(employee)
    work = (
        derive_current_work_status(session, employee.id)
        if session is not None
        else None
    )
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
        position=_display_position(employee) or employee.position,
        position_id=employee.position_id,
        manager_id=employee.manager_id,
        hire_date=employee.hire_date,
        employment_type=employee.employment_type,
        employment_end_date=employee.employment_end_date,
        employment_status=employee.employment_status,
        current_work_status=(
            work.current_work_status if work is not None else CurrentWorkStatus.ACTIVE
        ),
        current_leave=work.current_leave if work is not None else None,
        user_id=employee.user_id,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


def build_position_response(position: Position) -> PositionResponse:
    return PositionResponse(
        id=position.id,
        title=position.title,
        description=position.description,
        department_id=position.department_id,
        department=position.department.name if position.department else None,
        created_at=position.created_at,
        updated_at=position.updated_at,
    )


def build_organization_response(employee: Employee) -> EmployeeOrganizationResponse:
    position = None
    if employee.org_position is not None:
        position = build_position_response(employee.org_position)
    elif employee.position_id is not None:
        # fallback if relationship not loaded
        pass
    department = None
    if employee.department is not None:
        department = DepartmentResponse.model_validate(employee.department)
    manager = None
    if employee.manager is not None:
        manager = _person_summary(employee.manager)
    return EmployeeOrganizationResponse(
        employee=_person_summary(employee),
        position=position,
        department=department,
        manager=manager,
    )


def _person_summary(employee: Employee) -> OrgPersonSummary:
    return OrgPersonSummary(
        employee_id=employee.id,
        full_name=employee.full_name,
        position=_display_position(employee),
        department=employee.department.name if employee.department else None,
        has_profile_picture=bool(employee.profile_picture_storage_key),
    )


def _display_position(employee: Employee) -> str | None:
    if employee.org_position is not None:
        return employee.org_position.title
    return employee.position or None


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
