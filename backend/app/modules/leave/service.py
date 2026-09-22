from datetime import UTC, date, datetime

from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.hr_access import list_hr_staff_user_ids
from app.modules.leave.days import calculate_requested_days
from app.modules.leave.models import LeavePolicy, LeaveRequest, LeaveRequestStatus, LeaveType
from app.modules.leave.repository import LeaveRepository
from app.modules.leave.schemas import (
    LeaveBalanceResponse,
    LeavePolicyCreateRequest,
    LeavePolicyResponse,
    LeavePolicyUpdateRequest,
    LeaveRequestCreateRequest,
    LeaveRequestResponse,
    LeaveTypeCreateRequest,
    LeaveTypeResponse,
    LeaveTypeUpdateRequest,
)
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.shared.exceptions import AppException


def build_leave_type_response(leave_type: LeaveType) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(leave_type)


def build_leave_policy_response(policy: LeavePolicy) -> LeavePolicyResponse:
    return LeavePolicyResponse(
        id=policy.id,
        leave_type_id=policy.leave_type_id,
        leave_type_name=policy.leave_type.name if policy.leave_type else "",
        year=policy.year,
        days_allowed=policy.days_allowed,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def build_leave_request_response(request: LeaveRequest) -> LeaveRequestResponse:
    employee_name = None
    if request.employee is not None:
        employee_name = f"{request.employee.first_name} {request.employee.last_name}".strip()
    return LeaveRequestResponse(
        id=request.id,
        employee_id=request.employee_id,
        employee_name=employee_name,
        leave_type_id=request.leave_type_id,
        leave_type_name=request.leave_type.name if request.leave_type else "",
        start_date=request.start_date,
        end_date=request.end_date,
        requested_days=request.requested_days,
        reason=request.reason,
        rejection_reason=request.rejection_reason,
        status=request.status,
        approved_at=request.approved_at,
        rejected_at=request.rejected_at,
        reviewed_by=request.reviewed_by,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


class LeaveService:
    def __init__(
        self,
        repository: LeaveRepository,
        employees: EmployeeRepository,
        notifications: NotificationService | None = None,
    ):
        self.repository = repository
        self.employees = employees
        self.notifications = notifications

    # --- Types ---

    def list_types(self, *, active_only: bool = False) -> list[LeaveType]:
        return self.repository.list_types(active_only=active_only)

    def get_type(self, leave_type_id: int) -> LeaveType:
        leave_type = self.repository.get_type(leave_type_id)
        if leave_type is None:
            raise AppException("Leave type not found", status_code=404)
        return leave_type

    def create_type(self, payload: LeaveTypeCreateRequest) -> LeaveType:
        name = payload.name.strip()
        if self.repository.get_type_by_name(name) is not None:
            raise AppException("A leave type with this name already exists", status_code=409)
        description = payload.description.strip() if payload.description else None
        if description == "":
            description = None
        return self.repository.add_type(
            LeaveType(
                name=name,
                description=description,
                is_paid=payload.is_paid,
                is_active=payload.is_active,
            )
        )

    def update_type(self, leave_type_id: int, payload: LeaveTypeUpdateRequest) -> LeaveType:
        leave_type = self.get_type(leave_type_id)
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            name = data["name"].strip()
            existing = self.repository.get_type_by_name(name)
            if existing is not None and existing.id != leave_type.id:
                raise AppException("A leave type with this name already exists", status_code=409)
            leave_type.name = name
        if "description" in data:
            description = data["description"]
            if description is not None:
                description = description.strip() or None
            leave_type.description = description
        if "is_paid" in data and data["is_paid"] is not None:
            leave_type.is_paid = data["is_paid"]
        if "is_active" in data and data["is_active"] is not None:
            leave_type.is_active = data["is_active"]
        return self.repository.save_type(leave_type)

    def delete_type(self, leave_type_id: int) -> LeaveType:
        leave_type = self.get_type(leave_type_id)
        leave_type.is_active = False
        return self.repository.save_type(leave_type)

    # --- Policies ---

    def list_policies(
        self,
        *,
        leave_type_id: int | None = None,
        year: int | None = None,
    ) -> list[LeavePolicy]:
        return self.repository.list_policies(leave_type_id=leave_type_id, year=year)

    def get_policy(self, policy_id: int) -> LeavePolicy:
        policy = self.repository.get_policy(policy_id)
        if policy is None:
            raise AppException("Leave policy not found", status_code=404)
        return policy

    def create_policy(self, payload: LeavePolicyCreateRequest) -> LeavePolicy:
        leave_type = self.get_type(payload.leave_type_id)
        if not leave_type.is_active:
            raise AppException("Cannot create a policy for an inactive leave type", status_code=400)
        if self.repository.get_policy_for_type_year(payload.leave_type_id, payload.year):
            raise AppException(
                "A policy already exists for this leave type and year",
                status_code=409,
            )
        return self.repository.add_policy(
            LeavePolicy(
                leave_type_id=payload.leave_type_id,
                year=payload.year,
                days_allowed=payload.days_allowed,
            )
        )

    def update_policy(self, policy_id: int, payload: LeavePolicyUpdateRequest) -> LeavePolicy:
        policy = self.get_policy(policy_id)
        data = payload.model_dump(exclude_unset=True)
        next_year = data.get("year", policy.year)
        if "year" in data and data["year"] is not None:
            conflict = self.repository.get_policy_for_type_year(policy.leave_type_id, next_year)
            if conflict is not None and conflict.id != policy.id:
                raise AppException(
                    "A policy already exists for this leave type and year",
                    status_code=409,
                )
            policy.year = next_year
        if "days_allowed" in data and data["days_allowed"] is not None:
            policy.days_allowed = data["days_allowed"]
        return self.repository.save_policy(policy)

    def delete_policy(self, policy_id: int) -> None:
        policy = self.get_policy(policy_id)
        self.repository.delete_policy(policy)

    def get_days_allowed(
        self,
        employee_id: int,
        leave_type_id: int,
        year: int,
    ) -> int | None:
        """Company policy for type/year. Extension point for employee overrides later."""
        _ = employee_id
        policy = self.repository.get_policy_for_type_year(leave_type_id, year)
        if policy is None:
            return None
        return policy.days_allowed

    # --- Balances ---

    def get_balances(self, employee_id: int, year: int | None = None) -> list[LeaveBalanceResponse]:
        if self.employees.get_by_id(employee_id) is None:
            raise AppException("Employee not found", status_code=404)
        target_year = year if year is not None else datetime.now(UTC).year
        if target_year < 2000 or target_year > 2100:
            raise AppException("Invalid year", status_code=400)

        balances: list[LeaveBalanceResponse] = []
        for policy in self.repository.list_policies(year=target_year):
            if policy.leave_type is None or not policy.leave_type.is_active:
                continue
            days_used = self.repository.sum_requested_days(
                employee_id,
                policy.leave_type_id,
                target_year,
                LeaveRequestStatus.APPROVED,
            )
            days_pending = self.repository.sum_requested_days(
                employee_id,
                policy.leave_type_id,
                target_year,
                LeaveRequestStatus.PENDING,
            )
            balances.append(
                LeaveBalanceResponse(
                    employee_id=employee_id,
                    leave_type_id=policy.leave_type_id,
                    leave_type_name=policy.leave_type.name,
                    year=target_year,
                    days_allowed=policy.days_allowed,
                    days_used=days_used,
                    days_pending=days_pending,
                    days_available=policy.days_allowed - days_used,
                )
            )
        return balances

    def get_balances_for_user(
        self, user_id: int, year: int | None = None
    ) -> list[LeaveBalanceResponse]:
        employee = self._require_employee_for_user(user_id)
        return self.get_balances(employee.id, year=year)

    # --- Requests ---

    def list_requests_for_hr(
        self,
        *,
        employee_id: int | None = None,
        leave_type_id: int | None = None,
        status: LeaveRequestStatus | None = None,
    ) -> list[LeaveRequest]:
        return self.repository.list_requests(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            status=status,
        )

    def get_request_for_hr(self, request_id: int) -> LeaveRequest:
        request = self.repository.get_request(request_id)
        if request is None:
            raise AppException("Leave request not found", status_code=404)
        return request

    def list_requests_for_user(self, user_id: int) -> list[LeaveRequest]:
        employee = self._require_employee_for_user(user_id)
        return self.repository.list_requests(employee_id=employee.id)

    def get_request_for_user(self, user_id: int, request_id: int) -> LeaveRequest:
        employee = self._require_employee_for_user(user_id)
        request = self.repository.get_request(request_id)
        if request is None or request.employee_id != employee.id:
            raise AppException("Leave request not found", status_code=404)
        return request

    def create_request_for_user(
        self, user_id: int, payload: LeaveRequestCreateRequest
    ) -> LeaveRequest:
        employee = self._require_employee_for_user(user_id)
        return self._create_request(employee, payload)

    def cancel_request_for_user(self, user_id: int, request_id: int) -> LeaveRequest:
        request = self.get_request_for_user(user_id, request_id)
        if request.status != LeaveRequestStatus.PENDING:
            raise AppException("Only pending leave requests can be cancelled", status_code=400)
        request.status = LeaveRequestStatus.CANCELLED
        saved = self.repository.save_request(request)
        self._notify_cancelled(saved)
        return saved

    def approve_request(self, request_id: int, reviewer_user_id: int) -> LeaveRequest:
        request = self.get_request_for_hr(request_id)
        self._assert_can_review(request, reviewer_user_id)
        if request.status != LeaveRequestStatus.PENDING:
            raise AppException("Only pending leave requests can be approved", status_code=400)
        request.status = LeaveRequestStatus.APPROVED
        request.approved_at = datetime.now(UTC)
        request.rejected_at = None
        request.rejection_reason = None
        request.reviewed_by = reviewer_user_id
        saved = self.repository.save_request(request)
        self._notify_employee(
            saved,
            NotificationType.LEAVE_REQUEST_APPROVED,
            "Leave request approved",
            f"Your leave request ({saved.start_date} to {saved.end_date}) was approved.",
        )
        return saved

    def reject_request(
        self, request_id: int, reviewer_user_id: int, rejection_reason: str
    ) -> LeaveRequest:
        request = self.get_request_for_hr(request_id)
        self._assert_can_review(request, reviewer_user_id)
        if request.status != LeaveRequestStatus.PENDING:
            raise AppException("Only pending leave requests can be rejected", status_code=400)
        reason = rejection_reason.strip()
        if not reason:
            raise AppException("A rejection reason is required", status_code=400)
        request.status = LeaveRequestStatus.REJECTED
        request.rejected_at = datetime.now(UTC)
        request.approved_at = None
        request.rejection_reason = reason
        request.reviewed_by = reviewer_user_id
        saved = self.repository.save_request(request)
        self._notify_employee(
            saved,
            NotificationType.LEAVE_REQUEST_REJECTED,
            "Leave request rejected",
            f"Your leave request ({saved.start_date} to {saved.end_date}) was rejected. Reason: {reason}",
        )
        return saved

    def can_user_review_request(self, request: LeaveRequest, user_id: int) -> bool:
        if self._is_hr_staff_user(user_id):
            return True
        reviewer_employee = self.employees.get_by_user_id(user_id)
        if reviewer_employee is None:
            return False
        employee = self.employees.get_by_id(request.employee_id)
        return employee is not None and employee.manager_id == reviewer_employee.id

    def _assert_can_review(self, request: LeaveRequest, user_id: int) -> None:
        if not self.can_user_review_request(request, user_id):
            raise AppException("Not allowed to review this leave request", status_code=403)

    def _create_request(
        self, employee: Employee, payload: LeaveRequestCreateRequest
    ) -> LeaveRequest:
        if payload.end_date < payload.start_date:
            raise AppException(
                "End date must be on or after the start date.",
                status_code=400,
            )
        if payload.start_date.year != payload.end_date.year:
            raise AppException(
                "Leave requests cannot span multiple calendar years",
                status_code=400,
            )

        leave_type = self.get_type(payload.leave_type_id)
        if not leave_type.is_active:
            raise AppException("Leave type is inactive", status_code=400)

        year = payload.start_date.year
        days_allowed = self.get_days_allowed(employee.id, leave_type.id, year)
        if days_allowed is None:
            raise AppException(
                "No leave policy is configured for this leave type and year",
                status_code=400,
            )

        try:
            requested_days = calculate_requested_days(payload.start_date, payload.end_date)
        except ValueError as exc:
            raise AppException(
                "End date must be on or after the start date.",
                status_code=400,
            ) from exc

        if self.repository.find_overlapping(
            employee.id, payload.start_date, payload.end_date
        ):
            raise AppException(
                "You already have a pending or approved leave request that overlaps these dates. Choose different dates.",
                status_code=400,
            )

        days_used = self.repository.sum_requested_days(
            employee.id, leave_type.id, year, LeaveRequestStatus.APPROVED
        )
        days_pending = self.repository.sum_requested_days(
            employee.id, leave_type.id, year, LeaveRequestStatus.PENDING
        )
        available_for_new = days_allowed - days_used - days_pending
        if requested_days > available_for_new:
            raise AppException(
                "This request exceeds your available leave balance for this type.",
                status_code=400,
            )

        reason = payload.reason.strip() if payload.reason else None
        if reason == "":
            reason = None

        saved = self.repository.add_request(
            LeaveRequest(
                employee_id=employee.id,
                leave_type_id=leave_type.id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                requested_days=requested_days,
                reason=reason,
                status=LeaveRequestStatus.PENDING,
            )
        )
        self._notify_submitted(saved, employee)
        return saved

    def _require_employee_for_user(self, user_id: int) -> Employee:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        return employee

    def _is_hr_staff_user(self, user_id: int) -> bool:
        return user_id in set(list_hr_staff_user_ids(self.repository.db))

    def _notify_submitted(self, request: LeaveRequest, employee: Employee) -> None:
        if self.notifications is None:
            return
        employee_name = f"{employee.first_name} {employee.last_name}".strip()
        message = (
            f"{employee_name} requested {request.requested_days} day(s) "
            f"from {request.start_date} to {request.end_date}."
        )
        recipients = set(list_hr_staff_user_ids(self.repository.db))
        if employee.manager_id is not None:
            manager = self.employees.get_by_id(employee.manager_id)
            if manager is not None and manager.user_id is not None:
                recipients.add(manager.user_id)
        for recipient_id in recipients:
            if employee.user_id is not None and recipient_id == employee.user_id:
                continue
            self.notifications.create_if_absent(
                recipient_user_id=recipient_id,
                type=NotificationType.LEAVE_REQUEST_SUBMITTED,
                title="Leave request submitted",
                message=message,
                related_entity_type="leave_request",
                related_entity_id=request.id,
            )

    def _notify_cancelled(self, request: LeaveRequest) -> None:
        if self.notifications is None:
            return
        employee = self.employees.get_by_id(request.employee_id)
        employee_name = (
            f"{employee.first_name} {employee.last_name}".strip()
            if employee is not None
            else "An employee"
        )
        message = (
            f"{employee_name} cancelled a leave request "
            f"({request.start_date} to {request.end_date})."
        )
        recipients = set(list_hr_staff_user_ids(self.repository.db))
        if employee is not None and employee.manager_id is not None:
            manager = self.employees.get_by_id(employee.manager_id)
            if manager is not None and manager.user_id is not None:
                recipients.add(manager.user_id)
        for recipient_id in recipients:
            self.notifications.create_if_absent(
                recipient_user_id=recipient_id,
                type=NotificationType.LEAVE_REQUEST_CANCELLED,
                title="Leave request cancelled",
                message=message,
                related_entity_type="leave_request",
                related_entity_id=request.id,
            )

    def _notify_employee(
        self,
        request: LeaveRequest,
        notification_type: NotificationType,
        title: str,
        message: str,
    ) -> None:
        if self.notifications is None:
            return
        employee = self.employees.get_by_id(request.employee_id)
        if employee is None or employee.user_id is None:
            return
        self.notifications.create_if_absent(
            recipient_user_id=employee.user_id,
            type=notification_type,
            title=title,
            message=message,
            related_entity_type="leave_request",
            related_entity_id=request.id,
        )
