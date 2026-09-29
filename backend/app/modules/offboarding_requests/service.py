from datetime import UTC, datetime

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.hr_access import list_hr_staff_user_ids
from app.modules.identity.models import User
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.offboarding.models import OffboardingCase, OffboardingReason
from app.modules.offboarding.repository import OffboardingRepository
from app.modules.offboarding.schemas import OffboardingCreateRequest
from app.modules.offboarding.service import OffboardingService
from app.modules.offboarding_requests.models import (
    OffboardingRequest,
    OffboardingRequestStatus,
)
from app.modules.offboarding_requests.repository import OffboardingRequestRepository
from app.modules.offboarding_requests.schemas import (
    OffboardingRequestCreatePayload,
    OffboardingRequestDetailResponse,
    OffboardingRequestEmployeeSummary,
    OffboardingRequestEmployeeViewResponse,
    OffboardingRequestListItemResponse,
    OffboardingRequestReviewedBySummary,
    OffboardingRequestRejectPayload,
)
from app.shared.exceptions import AppException


class OffboardingRequestService:
    def __init__(
        self,
        repository: OffboardingRequestRepository,
        employees: EmployeeRepository,
        offboarding_cases: OffboardingRepository,
        notifications: NotificationService | None = None,
        offboarding_service: OffboardingService | None = None,
    ):
        self.repository = repository
        self.employees = employees
        self.offboarding_cases = offboarding_cases
        self.notifications = notifications
        self.offboarding_service = offboarding_service

    def create_for_user(
        self, user_id: int, payload: OffboardingRequestCreatePayload
    ) -> OffboardingRequest:
        employee = self._require_employee_for_user(user_id)
        if employee.employment_status != EmploymentStatus.ACTIVE:
            raise AppException("Employee must be active to request offboarding", status_code=400)

        today = datetime.now(UTC).date()
        if payload.requested_last_working_day < today:
            raise AppException(
                "Requested last working day cannot be in the past",
                status_code=400,
            )

        if self.offboarding_cases.get_active_for_employee(employee.id) is not None:
            raise AppException(
                "An active offboarding case already exists for this employee",
                status_code=409,
            )

        if self.repository.get_pending_for_employee(employee.id) is not None:
            raise AppException(
                "A pending offboarding request already exists",
                status_code=409,
            )

        reason_details = payload.reason_details.strip() if payload.reason_details else None
        if reason_details == "":
            reason_details = None

        saved = self.repository.add(
            OffboardingRequest(
                employee_id=employee.id,
                reason=OffboardingReason(payload.reason),
                reason_details=reason_details,
                requested_last_working_day=payload.requested_last_working_day,
                status=OffboardingRequestStatus.PENDING,
                submitted_at=datetime.now(UTC),
            )
        )
        self._notify_submitted(saved, employee)
        return saved

    def list_for_user(self, user_id: int) -> list[OffboardingRequest]:
        employee = self._require_employee_for_user(user_id)
        return self.repository.list_for_employee(employee.id)

    def get_for_user(self, user_id: int, request_id: int) -> OffboardingRequest:
        employee = self._require_employee_for_user(user_id)
        request = self.repository.get_by_id(request_id)
        if request is None or request.employee_id != employee.id:
            raise AppException("Offboarding request not found", status_code=404)
        return request

    def cancel_for_user(self, user_id: int, request_id: int) -> OffboardingRequest:
        request = self.get_for_user(user_id, request_id)
        if request.status != OffboardingRequestStatus.PENDING:
            raise AppException("Only pending requests can be cancelled", status_code=400)
        request.status = OffboardingRequestStatus.CANCELLED
        return self.repository.save(request)

    def list_for_hr(
        self,
        *,
        status: OffboardingRequestStatus | None = None,
        employee_id: int | None = None,
    ) -> list[OffboardingRequestListItemResponse]:
        return [
            build_list_item_response(item)
            for item in self.repository.list_for_hr(status=status, employee_id=employee_id)
        ]

    def get_for_hr(self, request_id: int) -> OffboardingRequest:
        request = self.repository.get_by_id(request_id)
        if request is None:
            raise AppException("Offboarding request not found", status_code=404)
        return request

    def approve(self, request_id: int, actor: User) -> OffboardingCase:
        if self.offboarding_service is None:
            raise AppException("Offboarding case service unavailable", status_code=500)

        request = self.get_for_hr(request_id)
        if request.status != OffboardingRequestStatus.PENDING:
            raise AppException("Only pending requests can be approved", status_code=400)

        # Create the case first so a failed create leaves the request PENDING.
        case = self.offboarding_service.create_for_hr(
            actor,
            self._case_payload_from_request(request),
        )

        request.status = OffboardingRequestStatus.APPROVED
        request.reviewed_by_user_id = actor.id
        request.reviewed_at = datetime.now(UTC)
        request.rejection_reason = None
        request.offboarding_case_id = case.id
        saved = self.repository.save(request)
        employee = self.employees.get_by_id(saved.employee_id)
        if employee is not None:
            self._notify_decision(saved, employee, approved=True)
        return case

    def reject(
        self,
        request_id: int,
        actor: User,
        payload: OffboardingRequestRejectPayload,
    ) -> OffboardingRequest:
        request = self.get_for_hr(request_id)
        if request.status != OffboardingRequestStatus.PENDING:
            raise AppException("Only pending requests can be rejected", status_code=400)

        rejection_reason = payload.rejection_reason.strip() if payload.rejection_reason else None
        if rejection_reason == "":
            rejection_reason = None

        request.status = OffboardingRequestStatus.REJECTED
        request.reviewed_by_user_id = actor.id
        request.reviewed_at = datetime.now(UTC)
        request.rejection_reason = rejection_reason
        saved = self.repository.save(request)
        employee = self.employees.get_by_id(saved.employee_id)
        if employee is not None:
            self._notify_decision(saved, employee, approved=False)
        return saved

    def link_case(self, request_id: int, offboarding_case_id: int) -> OffboardingRequest:
        request = self.get_for_hr(request_id)
        if request.status != OffboardingRequestStatus.APPROVED:
            raise AppException(
                "Only approved requests can be linked to a case",
                status_code=400,
            )
        if request.offboarding_case_id is not None:
            raise AppException("Request is already linked to a case", status_code=409)

        case = self.offboarding_cases.get_by_id(offboarding_case_id)
        if case is None:
            raise AppException("Offboarding case not found", status_code=404)
        if case.employee_id != request.employee_id:
            raise AppException(
                "Offboarding case does not belong to this employee",
                status_code=400,
            )

        request.offboarding_case_id = offboarding_case_id
        return self.repository.save(request)

    def create_case_for_hr(self, request_id: int, actor: User) -> OffboardingCase:
        """Recovery path: create a case for an already-approved, unlinked request."""
        if self.offboarding_service is None:
            raise AppException("Offboarding case service unavailable", status_code=500)

        request = self.get_for_hr(request_id)
        if request.status != OffboardingRequestStatus.APPROVED:
            raise AppException(
                "Only approved requests can create an offboarding case",
                status_code=400,
            )
        if request.offboarding_case_id is not None:
            raise AppException("Request is already linked to a case", status_code=409)

        case = self.offboarding_service.create_for_hr(
            actor,
            self._case_payload_from_request(request),
        )
        request.offboarding_case_id = case.id
        self.repository.save(request)
        return case

    def _case_payload_from_request(self, request: OffboardingRequest) -> OffboardingCreateRequest:
        return OffboardingCreateRequest(
            employee_id=request.employee_id,
            reason=request.reason,
            reason_details=request.reason_details,
            last_working_day=request.requested_last_working_day,
        )

    def _require_employee_for_user(self, user_id: int) -> Employee:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        return employee

    def _notify_submitted(self, request: OffboardingRequest, employee: Employee) -> None:
        if self.notifications is None:
            return
        employee_name = employee.full_name
        message = (
            f"{employee_name} submitted an offboarding request "
            f"(requested last day: {request.requested_last_working_day})."
        )
        for recipient_id in list_hr_staff_user_ids(self.repository.db):
            if employee.user_id is not None and recipient_id == employee.user_id:
                continue
            self.notifications.create_if_absent(
                recipient_user_id=recipient_id,
                type=NotificationType.OFFBOARDING_REQUEST_SUBMITTED,
                title="Offboarding request submitted",
                message=message,
                related_entity_type="offboarding_request",
                related_entity_id=request.id,
            )

    def _notify_decision(
        self,
        request: OffboardingRequest,
        employee: Employee,
        *,
        approved: bool,
    ) -> None:
        if self.notifications is None or employee.user_id is None:
            return
        if approved:
            self.notifications.create_if_absent(
                recipient_user_id=employee.user_id,
                type=NotificationType.OFFBOARDING_REQUEST_APPROVED,
                title="Offboarding request approved",
                message=(
                    "HR approved your offboarding request. "
                    "Your offboarding case has been opened."
                ),
                related_entity_type="offboarding_request",
                related_entity_id=request.id,
            )
        else:
            detail = (
                f" Reason: {request.rejection_reason}"
                if request.rejection_reason
                else ""
            )
            self.notifications.create_if_absent(
                recipient_user_id=employee.user_id,
                type=NotificationType.OFFBOARDING_REQUEST_REJECTED,
                title="Offboarding request rejected",
                message=f"HR rejected your offboarding request.{detail}",
                related_entity_type="offboarding_request",
                related_entity_id=request.id,
            )


def build_employee_summary(employee: Employee) -> OffboardingRequestEmployeeSummary:
    return OffboardingRequestEmployeeSummary(
        id=employee.id,
        full_name=employee.full_name,
        email=employee.email,
        position=employee.position,
        employee_number=employee.employee_number,
    )


def build_reviewed_by_summary(user: User | None) -> OffboardingRequestReviewedBySummary | None:
    if user is None:
        return None
    return OffboardingRequestReviewedBySummary(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
    )


def build_list_item_response(request: OffboardingRequest) -> OffboardingRequestListItemResponse:
    employee = request.employee
    return OffboardingRequestListItemResponse(
        id=request.id,
        employee_id=request.employee_id,
        employee_name=employee.full_name,
        employee_email=employee.email,
        position=employee.position,
        reason=request.reason,
        requested_last_working_day=request.requested_last_working_day,
        status=request.status,
        submitted_at=request.submitted_at,
        offboarding_case_id=request.offboarding_case_id,
    )


def build_detail_response(request: OffboardingRequest) -> OffboardingRequestDetailResponse:
    return OffboardingRequestDetailResponse(
        id=request.id,
        employee_id=request.employee_id,
        employee=build_employee_summary(request.employee),
        reason=request.reason,
        reason_details=request.reason_details,
        requested_last_working_day=request.requested_last_working_day,
        status=request.status,
        submitted_at=request.submitted_at,
        reviewed_by=build_reviewed_by_summary(request.reviewed_by),
        reviewed_at=request.reviewed_at,
        rejection_reason=request.rejection_reason,
        offboarding_case_id=request.offboarding_case_id,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def build_employee_view_response(
    request: OffboardingRequest,
) -> OffboardingRequestEmployeeViewResponse:
    return OffboardingRequestEmployeeViewResponse(
        id=request.id,
        reason=request.reason,
        reason_details=request.reason_details,
        requested_last_working_day=request.requested_last_working_day,
        status=request.status,
        submitted_at=request.submitted_at,
        reviewed_at=request.reviewed_at,
        rejection_reason=request.rejection_reason,
        offboarding_case_id=request.offboarding_case_id,
    )
