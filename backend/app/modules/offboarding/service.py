from datetime import UTC, datetime

from app.modules.employees.models import EmploymentStatus
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.models import User
from app.modules.offboarding.models import (
    OffboardingCase,
    OffboardingStatus,
)
from app.modules.offboarding.repository import OffboardingRepository
from app.modules.offboarding.schemas import (
    OffboardingCreateRequest,
    OffboardingCreatedBySummary,
    OffboardingDetailResponse,
    OffboardingEmployeeSummary,
    OffboardingEmployeeViewResponse,
    OffboardingListItemResponse,
)
from app.shared.exceptions import AppException


class OffboardingService:
    def __init__(
        self,
        repository: OffboardingRepository,
        employees: EmployeeRepository,
    ):
        self.repository = repository
        self.employees = employees

    def create_for_hr(self, actor: User, payload: OffboardingCreateRequest) -> OffboardingCase:
        employee = self.employees.get_by_id(payload.employee_id)
        if employee is None:
            raise AppException("Employee not found", status_code=404)
        if employee.employment_status != EmploymentStatus.ACTIVE:
            raise AppException("Employee must be active to start offboarding", status_code=400)

        initiated_at = datetime.now(UTC)
        if payload.last_working_day < initiated_at.date():
            raise AppException(
                "Last working day cannot be before the initiation date",
                status_code=400,
            )

        if self.repository.get_active_for_employee(payload.employee_id) is not None:
            raise AppException(
                "An active offboarding case already exists for this employee",
                status_code=409,
            )

        reason_details = payload.reason_details.strip() if payload.reason_details else None
        if reason_details == "":
            reason_details = None

        case = OffboardingCase(
            employee_id=payload.employee_id,
            reason=payload.reason,
            reason_details=reason_details,
            last_working_day=payload.last_working_day,
            status=OffboardingStatus.INITIATED,
            initiated_at=initiated_at,
            created_by_user_id=actor.id,
        )
        return self.repository.add(case)

    def list_for_hr(
        self,
        *,
        status: OffboardingStatus | None = None,
        employee_id: int | None = None,
    ) -> list[OffboardingListItemResponse]:
        return [
            build_list_item_response(case) for case in self.repository.list_for_hr(
                status=status,
                employee_id=employee_id,
            )
        ]

    def get_for_hr(self, case_id: int) -> OffboardingCase:
        case = self.repository.get_by_id(case_id)
        if case is None:
            raise AppException("Offboarding case not found", status_code=404)
        return case

    def list_for_user(self, user_id: int) -> list[OffboardingCase]:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee record not found for this user", status_code=404)
        return self.repository.list_for_employee(employee.id)

    def start(self, case_id: int) -> OffboardingCase:
        case = self.get_for_hr(case_id)
        allowed = {OffboardingStatus.INITIATED, OffboardingStatus.PENDING_CLEARANCE}
        if case.status not in allowed:
            raise AppException(
                f"Cannot start offboarding from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.IN_PROGRESS
        return self.repository.save(case)

    def move_to_pending_clearance(self, case_id: int) -> OffboardingCase:
        case = self.get_for_hr(case_id)
        if case.status != OffboardingStatus.IN_PROGRESS:
            raise AppException(
                f"Cannot move to pending clearance from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.PENDING_CLEARANCE
        return self.repository.save(case)

    def complete(self, case_id: int) -> OffboardingCase:
        """Complete when PENDING_CLEARANCE.

        Phase O.1 temporary rule: no checklist/clearance prerequisites yet —
        validates lifecycle + authorization only.
        """
        case = self.get_for_hr(case_id)
        if case.status != OffboardingStatus.PENDING_CLEARANCE:
            raise AppException(
                f"Cannot complete offboarding from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.COMPLETED
        case.completed_at = datetime.now(UTC)
        return self.repository.save(case)

    def cancel(self, case_id: int) -> OffboardingCase:
        case = self.get_for_hr(case_id)
        allowed = {
            OffboardingStatus.INITIATED,
            OffboardingStatus.IN_PROGRESS,
            OffboardingStatus.PENDING_CLEARANCE,
        }
        if case.status not in allowed:
            raise AppException(
                f"Cannot cancel offboarding from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.CANCELLED
        return self.repository.save(case)


def build_list_item_response(case: OffboardingCase) -> OffboardingListItemResponse:
    employee = case.employee
    return OffboardingListItemResponse(
        id=case.id,
        employee_id=case.employee_id,
        employee_name=employee.full_name,
        employee_email=employee.email,
        position=employee.position,
        reason=case.reason,
        last_working_day=case.last_working_day,
        status=case.status,
        initiated_at=case.initiated_at,
    )


def build_detail_response(case: OffboardingCase) -> OffboardingDetailResponse:
    employee = case.employee
    created_by = None
    if case.created_by is not None:
        created_by = OffboardingCreatedBySummary(
            id=case.created_by.id,
            full_name=f"{case.created_by.first_name} {case.created_by.last_name}".strip(),
            email=case.created_by.email,
        )
    return OffboardingDetailResponse(
        id=case.id,
        employee_id=case.employee_id,
        employee=OffboardingEmployeeSummary(
            id=employee.id,
            full_name=employee.full_name,
            email=employee.email,
            position=employee.position,
            employee_number=employee.employee_number,
        ),
        reason=case.reason,
        reason_details=case.reason_details,
        last_working_day=case.last_working_day,
        status=case.status,
        initiated_at=case.initiated_at,
        completed_at=case.completed_at,
        created_by=created_by,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def build_employee_view_response(case: OffboardingCase) -> OffboardingEmployeeViewResponse:
    return OffboardingEmployeeViewResponse(
        id=case.id,
        status=case.status,
        reason=case.reason,
        last_working_day=case.last_working_day,
        initiated_at=case.initiated_at,
        completed_at=case.completed_at,
    )
