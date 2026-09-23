from datetime import UTC, date, datetime, timedelta

from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.hr_access import list_admin_user_ids, list_hr_staff_user_ids
from app.modules.leave.approval import (
    ApprovalActor,
    classify_actor,
    resolve_requirements,
    would_finalize_after_manager,
)
from app.modules.leave.days import calculate_requested_days
from app.modules.leave.models import (
    LeaveApprovalStatus,
    LeavePolicy,
    LeaveRequest,
    LeaveRequestStatus,
    LeaveType,
)
from app.modules.leave.repository import LeaveRepository
from app.modules.leave.schemas import (
    CurrentLeaveSummary,
    CurrentWorkStatus,
    CurrentWorkStatusPayload,
    LeaveBalanceResponse,
    LeaveCalendarPeriod,
    LeaveCalendarResponse,
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
        manager_approval=request.manager_approval,
        manager_approved_by=request.manager_approved_by,
        manager_approved_at=request.manager_approved_at,
        hr_approval=request.hr_approval,
        hr_approved_by=request.hr_approved_by,
        hr_approved_at=request.hr_approved_at,
        admin_override=request.admin_override,
        admin_approved_by=request.admin_approved_by,
        admin_approved_at=request.admin_approved_at,
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
        employee = self.employees.get_by_id(request.employee_id)
        if employee is None:
            raise AppException("Leave request not found", status_code=404)

        if employee.user_id is not None and employee.user_id == reviewer_user_id:
            raise AppException("You cannot approve your own leave request", status_code=403)

        if request.status != LeaveRequestStatus.PENDING:
            raise AppException("Only pending leave requests can be approved", status_code=400)

        actor = classify_actor(self.repository.db, request, employee, reviewer_user_id)
        if actor is None:
            raise AppException("Not allowed to review this leave request", status_code=403)

        reqs = resolve_requirements(self.repository.db, request, employee)
        now = datetime.now(UTC)

        if actor == ApprovalActor.ADMIN:
            request.admin_override = LeaveApprovalStatus.APPROVED
            request.admin_approved_by = reviewer_user_id
            request.admin_approved_at = now
            self._mark_fully_approved(request, reviewer_user_id, now)
            saved = self.repository.save_request(request)
            self._notify_employee(
                saved,
                NotificationType.LEAVE_REQUEST_APPROVED,
                "Leave request approved",
                f"Your leave request ({saved.start_date} to {saved.end_date}) was approved.",
            )
            return saved

        if actor == ApprovalActor.MANAGER:
            if not reqs.manager_available:
                raise AppException(
                    "Manager approval is not required while the manager is on leave",
                    status_code=400,
                )
            if request.manager_approval == LeaveApprovalStatus.APPROVED:
                raise AppException("Manager has already approved this request", status_code=400)
            if employee.manager_id is None:
                raise AppException(
                    "This employee has no manager configured. An administrator must handle this request.",
                    status_code=400,
                )
            request.manager_approval = LeaveApprovalStatus.APPROVED
            request.manager_approved_by = reviewer_user_id
            request.manager_approved_at = now
            request.reviewed_by = reviewer_user_id

            if would_finalize_after_manager(reqs):
                self._mark_fully_approved(request, reviewer_user_id, now)
                saved = self.repository.save_request(request)
                self._notify_employee(
                    saved,
                    NotificationType.LEAVE_REQUEST_APPROVED,
                    "Leave request approved",
                    f"Your leave request ({saved.start_date} to {saved.end_date}) was approved.",
                )
                return saved

            saved = self.repository.save_request(request)
            # Recompute with manager satisfied for HR notify list
            refreshed = resolve_requirements(self.repository.db, saved, employee)
            self._notify_manager_approved(saved, employee, refreshed.available_hr_user_ids)
            return saved

        if actor == ApprovalActor.HR:
            if reqs.requester_is_hr:
                raise AppException(
                    "HR cannot approve this leave request; the requester's manager or an administrator must review it",
                    status_code=403,
                )
            # Manager must approve first when manager is available and not yet done
            if reqs.manager_available and request.manager_approval != LeaveApprovalStatus.APPROVED:
                raise AppException(
                    "Manager approval is required before HR can approve this request",
                    status_code=400,
                )
            if not reqs.hr_available and request.manager_approval == LeaveApprovalStatus.APPROVED:
                raise AppException(
                    "HR approval is not required while no HR approvers are available",
                    status_code=400,
                )
            if not reqs.hr_available and not reqs.manager_available:
                raise AppException(
                    "No HR approvers are available. An administrator must handle this request.",
                    status_code=400,
                )
            if request.hr_approval == LeaveApprovalStatus.APPROVED:
                raise AppException("HR has already approved this request", status_code=400)

            request.hr_approval = LeaveApprovalStatus.APPROVED
            request.hr_approved_by = reviewer_user_id
            request.hr_approved_at = now
            self._mark_fully_approved(request, reviewer_user_id, now)
            saved = self.repository.save_request(request)
            self._notify_employee(
                saved,
                NotificationType.LEAVE_REQUEST_APPROVED,
                "Leave request approved",
                f"Your leave request ({saved.start_date} to {saved.end_date}) was approved.",
            )
            return saved

        raise AppException("Not allowed to review this leave request", status_code=403)

    def reject_request(
        self, request_id: int, reviewer_user_id: int, rejection_reason: str
    ) -> LeaveRequest:
        request = self.get_request_for_hr(request_id)
        if request.status != LeaveRequestStatus.PENDING:
            raise AppException("Only pending leave requests can be rejected", status_code=400)

        employee = self.employees.get_by_id(request.employee_id)
        if employee is None:
            raise AppException("Leave request not found", status_code=404)

        if employee.user_id is not None and employee.user_id == reviewer_user_id:
            raise AppException("You cannot reject your own leave request", status_code=403)

        actor = classify_actor(self.repository.db, request, employee, reviewer_user_id)
        if actor is None:
            raise AppException("Not allowed to review this leave request", status_code=403)

        # HR cannot reject HR self-leave (same as approve)
        reqs = resolve_requirements(self.repository.db, request, employee)
        if actor == ApprovalActor.HR and reqs.requester_is_hr:
            raise AppException(
                "HR cannot reject this leave request; the requester's manager or an administrator must review it",
                status_code=403,
            )

        if actor == ApprovalActor.MANAGER:
            if employee.manager_id is None:
                raise AppException(
                    "This employee has no manager configured. An administrator must handle this request.",
                    status_code=400,
                )
            if request.manager_approval != LeaveApprovalStatus.PENDING:
                raise AppException("Manager has already reviewed this request", status_code=400)

        if actor == ApprovalActor.HR:
            if reqs.manager_available and request.manager_approval != LeaveApprovalStatus.APPROVED:
                raise AppException(
                    "Manager approval is required before HR can reject this request",
                    status_code=400,
                )
            if request.hr_approval != LeaveApprovalStatus.PENDING:
                raise AppException("HR has already reviewed this request", status_code=400)

        reason = rejection_reason.strip()
        if not reason:
            raise AppException("A rejection reason is required", status_code=400)

        now = datetime.now(UTC)
        if actor == ApprovalActor.MANAGER:
            request.manager_approval = LeaveApprovalStatus.REJECTED
            request.manager_approved_by = reviewer_user_id
            request.manager_approved_at = now
        elif actor == ApprovalActor.HR:
            request.hr_approval = LeaveApprovalStatus.REJECTED
            request.hr_approved_by = reviewer_user_id
            request.hr_approved_at = now
        elif actor == ApprovalActor.ADMIN:
            request.admin_override = LeaveApprovalStatus.REJECTED
            request.admin_approved_by = reviewer_user_id
            request.admin_approved_at = now

        request.status = LeaveRequestStatus.REJECTED
        request.rejected_at = now
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

    def _mark_fully_approved(
        self, request: LeaveRequest, reviewer_user_id: int, now: datetime
    ) -> None:
        self._assert_can_finalize_approval(request)
        request.status = LeaveRequestStatus.APPROVED
        request.approved_at = now
        request.rejected_at = None
        request.rejection_reason = None
        request.reviewed_by = reviewer_user_id

    def _assert_can_finalize_approval(self, request: LeaveRequest) -> None:
        """Re-check overlap and balance at final approval time."""
        if self.repository.find_overlapping(
            request.employee_id,
            request.start_date,
            request.end_date,
            exclude_request_id=request.id,
        ):
            raise AppException(
                "Cannot approve: another pending or approved leave request overlaps these dates.",
                status_code=400,
            )

        year = request.start_date.year
        days_allowed = self.get_days_allowed(request.employee_id, request.leave_type_id, year)
        if days_allowed is None:
            raise AppException(
                "No leave policy is configured for this leave type and year",
                status_code=400,
            )
        days_used = self.repository.sum_requested_days(
            request.employee_id, request.leave_type_id, year, LeaveRequestStatus.APPROVED
        )
        # Other pending requests still consume headroom; this request is about to leave pending.
        days_pending_others = self.repository.sum_requested_days(
            request.employee_id, request.leave_type_id, year, LeaveRequestStatus.PENDING
        ) - request.requested_days
        if days_pending_others < 0:
            days_pending_others = 0
        available = days_allowed - days_used - days_pending_others
        if request.requested_days > available:
            raise AppException(
                "Cannot approve: this request exceeds the available leave balance for this type.",
                status_code=400,
            )

    def get_calendar_for_employee(
        self, employee_id: int, year: int, month: int
    ) -> LeaveCalendarResponse:
        if month < 1 or month > 12:
            raise AppException("month must be between 1 and 12", status_code=400)
        if self.employees.get_by_id(employee_id) is None:
            raise AppException("Employee not found", status_code=404)
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year, 12, 31)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        periods = self.repository.list_calendar_periods(
            employee_id, month_start=month_start, month_end=month_end
        )
        return LeaveCalendarResponse(
            year=year,
            month=month,
            periods=[
                LeaveCalendarPeriod(
                    request_id=item.id,
                    leave_type_name=item.leave_type.name if item.leave_type else "",
                    status=item.status,
                    start_date=item.start_date,
                    end_date=item.end_date,
                )
                for item in periods
            ],
        )

    def get_calendar_for_user(self, user_id: int, year: int, month: int) -> LeaveCalendarResponse:
        employee = self._require_employee_for_user(user_id)
        return self.get_calendar_for_employee(employee.id, year, month)

    def get_current_work_status(
        self, employee_id: int, *, as_of: date | None = None
    ) -> CurrentWorkStatusPayload:
        if self.employees.get_by_id(employee_id) is None:
            raise AppException("Employee not found", status_code=404)
        day = as_of or date.today()
        covering = self.repository.find_approved_covering(employee_id, day)
        if covering is None:
            return CurrentWorkStatusPayload(
                current_work_status=CurrentWorkStatus.ACTIVE,
                current_leave=None,
            )
        return CurrentWorkStatusPayload(
            current_work_status=CurrentWorkStatus.ON_LEAVE,
            current_leave=CurrentLeaveSummary(
                leave_type=covering.leave_type.name if covering.leave_type else "",
                start_date=covering.start_date,
                end_date=covering.end_date,
            ),
        )

    def list_team_requests_for_user(
        self, user_id: int, *, status: LeaveRequestStatus | None = LeaveRequestStatus.PENDING
    ) -> list[LeaveRequest]:
        manager = self._require_employee_for_user(user_id)
        report_ids = self.employees.list_direct_report_ids(manager.id)
        return self.repository.list_requests_for_employees(report_ids, status=status)

    def can_user_review_request(self, request: LeaveRequest, user_id: int) -> bool:
        if request.status != LeaveRequestStatus.PENDING:
            return False
        employee = self.employees.get_by_id(request.employee_id)
        if employee is None:
            return False
        if employee.user_id is not None and employee.user_id == user_id:
            return False

        actor = classify_actor(self.repository.db, request, employee, user_id)
        if actor is None:
            return False

        reqs = resolve_requirements(self.repository.db, request, employee)
        if actor == ApprovalActor.ADMIN:
            return True
        if actor == ApprovalActor.MANAGER:
            return reqs.manager_available and request.manager_approval == LeaveApprovalStatus.PENDING
        if actor == ApprovalActor.HR:
            if reqs.requester_is_hr:
                return False
            if reqs.manager_available and request.manager_approval != LeaveApprovalStatus.APPROVED:
                return False
            return reqs.hr_available and request.hr_approval == LeaveApprovalStatus.PENDING
        return False

    def _assert_can_review(self, request: LeaveRequest, user_id: int) -> None:
        """Legacy helper kept for callers; prefer can_user_review_request."""
        if not self.can_user_review_request(request, user_id):
            employee = self.employees.get_by_id(request.employee_id)
            if employee is not None and employee.user_id == user_id:
                raise AppException("You cannot approve your own leave request", status_code=403)
            if employee is not None and employee.manager_id is None and not self._is_admin_user(user_id):
                raise AppException(
                    "This employee has no manager configured. An administrator must handle this request.",
                    status_code=400,
                )
            raise AppException("Not allowed to review this leave request", status_code=403)

    def _is_hr_staff_user(self, user_id: int) -> bool:
        return user_id in set(list_hr_staff_user_ids(self.repository.db))

    def _is_admin_user(self, user_id: int) -> bool:
        return user_id in set(list_admin_user_ids(self.repository.db))

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
                manager_approval=LeaveApprovalStatus.PENDING,
                hr_approval=LeaveApprovalStatus.PENDING,
                admin_override=LeaveApprovalStatus.PENDING,
            )
        )
        self._notify_submitted(saved, employee)
        return saved

    def _require_employee_for_user(self, user_id: int) -> Employee:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        return employee

    def _notify_submitted(self, request: LeaveRequest, employee: Employee) -> None:
        if self.notifications is None:
            return
        employee_name = f"{employee.first_name} {employee.last_name}".strip()
        message = (
            f"{employee_name} requested {request.requested_days} day(s) "
            f"from {request.start_date} to {request.end_date}."
        )
        reqs = resolve_requirements(self.repository.db, request, employee)
        recipients: set[int] = set()
        if reqs.manager_user_id is not None and reqs.manager_available:
            recipients.add(reqs.manager_user_id)
        if not reqs.requester_is_hr:
            # Notify HR when the HR step will be needed (or is already actionable)
            if reqs.hr_available:
                recipients.update(reqs.available_hr_user_ids)
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

    def _notify_manager_approved(
        self, request: LeaveRequest, employee: Employee, hr_user_ids: list[int]
    ) -> None:
        if self.notifications is None:
            return
        employee_name = f"{employee.first_name} {employee.last_name}".strip()
        message = (
            f"Manager approved {employee_name}'s leave request "
            f"({request.start_date} to {request.end_date}). HR approval is required."
        )
        for recipient_id in hr_user_ids:
            if employee.user_id is not None and recipient_id == employee.user_id:
                continue
            self.notifications.create_if_absent(
                recipient_user_id=recipient_id,
                type=NotificationType.LEAVE_REQUEST_MANAGER_APPROVED,
                title="Leave awaiting HR approval",
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
        recipients: set[int] = set()
        if employee is not None:
            reqs = resolve_requirements(self.repository.db, request, employee)
            if reqs.manager_user_id is not None:
                recipients.add(reqs.manager_user_id)
            recipients.update(reqs.available_hr_user_ids)
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
