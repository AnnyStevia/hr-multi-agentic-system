"""HR Leave Agent read tools — wrap LeaveService only (no repositories / DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field, model_validator

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.leave.models import LeaveCancellationStatus, LeaveRequestStatus
from app.modules.leave.service import (
    LeaveService,
    build_leave_policy_response,
    build_leave_request_response,
)
from app.shared.exceptions import AppException

_READ_META = ToolMetadata(
    operation="read",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"leaves:read"}),
    operates_on_current_user=False,
)


def _call_service(fn, *, error_message: str):
    try:
        return fn()
    except AppException as exc:
        raise ToolExecutionError(exc.message) from exc
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(error_message) from exc


def _utc_today() -> date:
    return datetime.now(UTC).date()


# --- Shared compact shapes ---


class LeaveBalanceItem(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int
    leave_type_name: str
    days_allowed: int
    days_used: int
    days_pending: int
    days_available: int


class LeaveRequestSummary(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int
    employee_id: int
    employee_name: str | None = None
    leave_type_id: int
    leave_type_name: str
    start_date: date
    end_date: date
    requested_days: int
    status: str
    cancellation_status: str
    reason: str | None = None
    manager_approval: str
    hr_approval: str


class OnLeaveItem(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int
    employee_id: int
    employee_name: str | None = None
    leave_type_name: str
    start_date: date
    end_date: date
    cancellation_status: str


class LeaveTypeItem(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int
    name: str
    is_paid: bool


def _request_summary(request) -> LeaveRequestSummary:
    dto = build_leave_request_response(request)
    return LeaveRequestSummary(
        request_id=dto.id,
        employee_id=dto.employee_id,
        employee_name=dto.employee_name,
        leave_type_id=dto.leave_type_id,
        leave_type_name=dto.leave_type_name,
        start_date=dto.start_date,
        end_date=dto.end_date,
        requested_days=dto.requested_days,
        status=dto.status.value if hasattr(dto.status, "value") else str(dto.status),
        cancellation_status=(
            dto.cancellation_status.value
            if hasattr(dto.cancellation_status, "value")
            else str(dto.cancellation_status)
        ),
        reason=dto.reason,
        manager_approval=(
            dto.manager_approval.value
            if hasattr(dto.manager_approval, "value")
            else str(dto.manager_approval)
        ),
        hr_approval=(
            dto.hr_approval.value if hasattr(dto.hr_approval, "value") else str(dto.hr_approval)
        ),
    )


# --- get_leave_balance ---


class GetLeaveBalanceInput(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int = Field(
        ge=1,
        description="Employee ID from find_employees (do not invent).",
    )
    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Calendar year (UTC). Omit for current UTC year. Must be 2000–2100.",
    )


class GetLeaveBalanceOutput(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    year: int
    balances: list[LeaveBalanceItem] = Field(default_factory=list)
    note: str = (
        "days_available is days_allowed minus days_used only; "
        "pending requests are listed separately and are reserved on create/approve."
    )


class GetLeaveBalanceTool(BaseTool):
    name = "get_leave_balance"
    description = (
        "Return leave balances for an employee for a year (default: current UTC year): "
        "days_allowed, days_used, days_pending, days_available per active leave type with a policy. "
        "Report these integers exactly; do not recalculate. "
        "days_available does not subtract pending; treat days_pending as reserved headroom. "
        "Empty balances mean no policies for that year — do not invent allowances. "
        "Resolve employee names with find_employees first. Read-only. Requires HR/admin + leaves:read."
    )
    metadata = _READ_META
    input_model = GetLeaveBalanceInput
    output_model = GetLeaveBalanceOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetLeaveBalanceInput)
        rows = _call_service(
            lambda: self._leave.get_balances(args.employee_id, year=args.year),
            error_message="Failed to retrieve leave balances",
        )
        if rows:
            year = rows[0].year
        elif args.year is not None:
            year = args.year
        else:
            year = datetime.now(UTC).year
        return GetLeaveBalanceOutput(
            employee_id=args.employee_id,
            year=year,
            balances=[
                LeaveBalanceItem(
                    leave_type_id=r.leave_type_id,
                    leave_type_name=r.leave_type_name,
                    days_allowed=r.days_allowed,
                    days_used=r.days_used,
                    days_pending=r.days_pending,
                    days_available=r.days_available,
                )
                for r in rows
            ],
        )


# --- get_leave_request ---


class GetLeaveRequestInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1, description="Leave request ID (do not invent).")


class GetLeaveRequestOutput(BaseModel):
    model_config = {"extra": "forbid"}

    request: LeaveRequestSummary


class GetLeaveRequestTool(BaseTool):
    name = "get_leave_request"
    description = (
        "Get one leave request by request_id: status (pending|approved|rejected|cancelled), "
        "cancellation_status (none|requested|rejected), dates, dual approvals. "
        "pending is not approved; cancellation_status=requested is not cancelled. "
        "Read-only. Requires HR/admin + leaves:read."
    )
    metadata = _READ_META
    input_model = GetLeaveRequestInput
    output_model = GetLeaveRequestOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetLeaveRequestInput)
        request = _call_service(
            lambda: self._leave.get_request_for_hr(args.request_id),
            error_message="Failed to load leave request",
        )
        return GetLeaveRequestOutput(request=_request_summary(request))


# --- list_leave_requests ---


class ListLeaveRequestsInput(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int | None = Field(
        default=None,
        ge=1,
        description="Filter by employee_id from find_employees.",
    )
    leave_type_id: int | None = Field(
        default=None,
        ge=1,
        description="Filter by leave_type_id from list_leave_types.",
    )
    status: str | None = Field(
        default=None,
        description="pending | approved | rejected | cancelled",
    )
    cancellation_status: str | None = Field(
        default=None,
        description="none | requested | rejected",
    )
    overlaps_start: date | None = Field(
        default=None,
        description="Inclusive start of date window (YYYY-MM-DD). Pair with overlaps_end for a month.",
    )
    overlaps_end: date | None = Field(
        default=None,
        description="Inclusive end of date window (YYYY-MM-DD).",
    )
    limit: int = Field(default=50, ge=1, le=100, description="Max rows to return.")


class ListLeaveRequestsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    count: int
    requests: list[LeaveRequestSummary]


def _parse_status(raw: str | None) -> LeaveRequestStatus | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return LeaveRequestStatus(str(raw).strip().lower())
    except ValueError as exc:
        raise ToolExecutionError(
            "status must be pending, approved, rejected, or cancelled"
        ) from exc


def _parse_cancellation(raw: str | None) -> LeaveCancellationStatus | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return LeaveCancellationStatus(str(raw).strip().lower())
    except ValueError as exc:
        raise ToolExecutionError(
            "cancellation_status must be none, requested, or rejected"
        ) from exc


class ListLeaveRequestsTool(BaseTool):
    name = "list_leave_requests"
    description = (
        "List leave requests with optional filters: employee_id, leave_type_id, "
        "status, cancellation_status, overlaps_start/overlaps_end (date overlap window). "
        "For 'this month', set overlaps_start/end to the month bounds. "
        "Do not treat pending as approved or cancellation requested as cancelled. "
        "Read-only. Requires HR/admin + leaves:read."
    )
    metadata = _READ_META
    input_model = ListLeaveRequestsInput
    output_model = ListLeaveRequestsOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListLeaveRequestsInput)
        status = _parse_status(args.status)
        cancellation = _parse_cancellation(args.cancellation_status)
        rows = _call_service(
            lambda: self._leave.list_requests_for_hr(
                employee_id=args.employee_id,
                leave_type_id=args.leave_type_id,
                status=status,
                cancellation_status=cancellation,
                overlaps_start=args.overlaps_start,
                overlaps_end=args.overlaps_end,
            ),
            error_message="Failed to list leave requests",
        )
        capped = rows[: args.limit]
        return ListLeaveRequestsOutput(
            count=len(capped),
            requests=[_request_summary(r) for r in capped],
        )


# --- list_pending_leave_requests ---


class ListPendingLeaveRequestsInput(BaseModel):
    model_config = {"extra": "forbid"}

    limit: int = Field(default=50, ge=1, le=100, description="Max rows to return.")


class ListPendingLeaveRequestsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    count: int
    requests: list[LeaveRequestSummary]


class ListPendingLeaveRequestsTool(BaseTool):
    name = "list_pending_leave_requests"
    description = (
        "List leave requests with status=pending (approval queue only). "
        "Does not include approved leave with cancellation_status=requested. "
        "Read-only. Requires HR/admin + leaves:read."
    )
    metadata = _READ_META
    input_model = ListPendingLeaveRequestsInput
    output_model = ListPendingLeaveRequestsOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListPendingLeaveRequestsInput)
        rows = _call_service(
            lambda: self._leave.list_requests_for_hr(status=LeaveRequestStatus.PENDING),
            error_message="Failed to list pending leave requests",
        )
        capped = rows[: args.limit]
        return ListPendingLeaveRequestsOutput(
            count=len(capped),
            requests=[_request_summary(r) for r in capped],
        )


# --- list_currently_on_leave ---


class ListCurrentlyOnLeaveInput(BaseModel):
    model_config = {"extra": "forbid"}

    as_of: date | None = Field(
        default=None,
        description="Date to check (YYYY-MM-DD). Defaults to current UTC date.",
    )


class ListCurrentlyOnLeaveOutput(BaseModel):
    model_config = {"extra": "forbid"}

    as_of: date
    count: int
    items: list[OnLeaveItem]


class ListCurrentlyOnLeaveTool(BaseTool):
    name = "list_currently_on_leave"
    description = (
        "List employees with an approved leave covering as_of (default: current UTC date). "
        "Includes approved leave with cancellation_status=requested (still on leave). "
        "Excludes pending, rejected, and cancelled requests. "
        "Read-only. Requires HR/admin + leaves:read."
    )
    metadata = _READ_META
    input_model = ListCurrentlyOnLeaveInput
    output_model = ListCurrentlyOnLeaveOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListCurrentlyOnLeaveInput)
        day = args.as_of or _utc_today()
        rows = _call_service(
            lambda: self._leave.list_currently_on_leave(as_of=day),
            error_message="Failed to list employees currently on leave",
        )
        items: list[OnLeaveItem] = []
        for request in rows:
            name = None
            if request.employee is not None:
                name = f"{request.employee.first_name} {request.employee.last_name}".strip()
            cancel = request.cancellation_status
            items.append(
                OnLeaveItem(
                    request_id=request.id,
                    employee_id=request.employee_id,
                    employee_name=name,
                    leave_type_name=(
                        request.leave_type.name if request.leave_type else ""
                    ),
                    start_date=request.start_date,
                    end_date=request.end_date,
                    cancellation_status=(
                        cancel.value if hasattr(cancel, "value") else str(cancel)
                    ),
                )
            )
        return ListCurrentlyOnLeaveOutput(as_of=day, count=len(items), items=items)


# --- list_leave_types ---


class ListLeaveTypesInput(BaseModel):
    model_config = {"extra": "forbid"}

    active_only: bool = Field(
        default=True,
        description="If true, only active leave types.",
    )


class ListLeaveTypesOutput(BaseModel):
    model_config = {"extra": "forbid"}

    count: int
    leave_types: list[LeaveTypeItem]


class ListLeaveTypesTool(BaseTool):
    name = "list_leave_types"
    description = (
        "List leave types (id, name, is_paid) for policy and balance questions. "
        "Use before get_leave_policy when the user names a leave type. "
        "Do not invent type names or IDs. Read-only. Requires HR/admin + leaves:read."
    )
    metadata = _READ_META
    input_model = ListLeaveTypesInput
    output_model = ListLeaveTypesOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListLeaveTypesInput)
        rows = _call_service(
            lambda: self._leave.list_types(active_only=args.active_only),
            error_message="Failed to list leave types",
        )
        items = [
            LeaveTypeItem(
                leave_type_id=t.id,
                name=t.name,
                is_paid=bool(t.is_paid),
            )
            for t in rows
        ]
        return ListLeaveTypesOutput(count=len(items), leave_types=items)


# --- get_leave_policy ---


class GetLeavePolicyInput(BaseModel):
    model_config = {"extra": "forbid"}

    policy_id: int | None = Field(default=None, ge=1, description="Policy ID.")
    leave_type_id: int | None = Field(
        default=None,
        ge=1,
        description="Leave type ID (with year).",
    )
    leave_type_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Exact leave type name (with year). Prefer list_leave_types first.",
    )
    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Policy year (required with leave_type_id or leave_type_name).",
    )

    @model_validator(mode="after")
    def _require_lookup(self):
        modes = 0
        if self.policy_id is not None:
            modes += 1
        if self.leave_type_id is not None and self.year is not None:
            modes += 1
        if self.leave_type_name is not None and self.year is not None:
            modes += 1
        if modes == 1:
            return self
        raise ValueError(
            "Provide exactly one of: policy_id; leave_type_id+year; leave_type_name+year"
        )


class GetLeavePolicyOutput(BaseModel):
    model_config = {"extra": "forbid"}

    policy_id: int
    leave_type_id: int
    leave_type_name: str
    year: int
    days_allowed: int


class GetLeavePolicyTool(BaseTool):
    name = "get_leave_policy"
    description = (
        "Get a leave policy by policy_id, or leave_type_id+year, or leave_type_name+year. "
        "Do not invent days_allowed — if not found, report that clearly. "
        "Read-only. Requires HR/admin + leaves:read."
    )
    metadata = _READ_META
    input_model = GetLeavePolicyInput
    output_model = GetLeavePolicyOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetLeavePolicyInput)
        if args.policy_id is not None:
            policy = _call_service(
                lambda: self._leave.get_policy(args.policy_id),
                error_message="Failed to load leave policy",
            )
        elif args.leave_type_name is not None:
            assert args.year is not None
            leave_type = _call_service(
                lambda: self._leave.get_type_by_name(args.leave_type_name),
                error_message="Failed to resolve leave type",
            )
            policy = _call_service(
                lambda: self._leave.get_policy_for_type_year(leave_type.id, args.year),
                error_message="Failed to load leave policy",
            )
        else:
            assert args.leave_type_id is not None and args.year is not None
            policy = _call_service(
                lambda: self._leave.get_policy_for_type_year(
                    args.leave_type_id, args.year
                ),
                error_message="Failed to load leave policy",
            )
        dto = build_leave_policy_response(policy)
        return GetLeavePolicyOutput(
            policy_id=dto.id,
            leave_type_id=dto.leave_type_id,
            leave_type_name=dto.leave_type_name,
            year=dto.year,
            days_allowed=dto.days_allowed,
        )
