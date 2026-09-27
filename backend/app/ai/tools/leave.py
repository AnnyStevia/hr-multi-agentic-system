"""Self-scoped Leave Agent read tools (authenticated employee's own data)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.leave.models import LeaveRequestStatus
from app.modules.leave.schemas import LeaveBalanceResponse
from app.modules.leave.service import LeaveService, build_leave_request_response
from app.shared.exceptions import AppException

_SELF_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset({"leaves:read"}),
    operates_on_current_user=True,
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


def _require_employee_id(context: AIExecutionContext) -> int:
    if context.employee_id is None:
        raise ToolExecutionError("No employee profile for the authenticated user")
    return context.employee_id


class LeaveBalanceItem(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int
    leave_type_name: str
    days_allowed: int
    days_used: int
    days_pending: int
    days_available: int


class MyLeaveRequestSummary(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int
    leave_type_id: int
    leave_type_name: str
    start_date: date
    end_date: date
    requested_days: int
    status: str
    cancellation_status: str
    reason: str | None = None


def _my_request_summary(request) -> MyLeaveRequestSummary:
    dto = build_leave_request_response(request)
    return MyLeaveRequestSummary(
        request_id=dto.id,
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
    )


def _balances_output(
    employee_id: int, rows: list[LeaveBalanceResponse], year: int | None = None
):
    if rows:
        resolved_year = rows[0].year
    elif year is not None:
        resolved_year = year
    else:
        resolved_year = datetime.now(UTC).year
    return GetMyLeaveBalanceOutput(
        employee_id=employee_id,
        year=resolved_year,
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
        note=(
            "days_available is days_allowed minus days_used only; "
            "pending requests are listed separately and are reserved on create/approve."
        ),
    )


# --- get_my_leave_balance ---


class GetMyLeaveBalanceInput(BaseModel):
    """No identity arguments — employee comes only from AIExecutionContext."""

    model_config = {"extra": "forbid"}

    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Calendar year (UTC). Omit for current UTC year.",
    )


class GetMyLeaveBalanceOutput(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    year: int
    balances: list[LeaveBalanceItem] = Field(default_factory=list)
    note: str = (
        "days_available is days_allowed minus days_used only; "
        "pending requests are listed separately and are reserved on create/approve."
    )


class GetMyLeaveBalanceTool(BaseTool):
    name = "get_my_leave_balance"
    description = (
        "Return the authenticated employee's leave balances "
        "(days_allowed, days_used, days_pending, days_available). "
        "Use for 'my balance' / 'how many days do I have'. "
        "Does not accept employee_id. Read-only."
    )
    metadata = _SELF_META
    input_model = GetMyLeaveBalanceInput
    output_model = GetMyLeaveBalanceOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetMyLeaveBalanceInput)
        employee_id = _require_employee_id(context)
        rows = _call_service(
            lambda: self._leave.get_balances(employee_id, year=args.year),
            error_message="Failed to retrieve leave balances",
        )
        return _balances_output(employee_id, rows, year=args.year)


# --- list_my_leave_requests ---


class ListMyLeaveRequestsInput(BaseModel):
    model_config = {"extra": "forbid"}

    status: str | None = Field(
        default=None,
        description="pending | approved | rejected | cancelled",
    )
    limit: int = Field(default=50, ge=1, le=100)


class ListMyLeaveRequestsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    count: int
    requests: list[MyLeaveRequestSummary]


class ListMyLeaveRequestsTool(BaseTool):
    name = "list_my_leave_requests"
    description = (
        "List the authenticated employee's own leave requests. "
        "Optional status filter. Does not accept employee_id. Read-only."
    )
    metadata = _SELF_META
    input_model = ListMyLeaveRequestsInput
    output_model = ListMyLeaveRequestsOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListMyLeaveRequestsInput)
        _require_employee_id(context)
        rows = _call_service(
            lambda: self._leave.list_requests_for_user(context.user_id),
            error_message="Failed to list leave requests",
        )
        if args.status:
            try:
                wanted = LeaveRequestStatus(args.status.strip().lower())
            except ValueError as exc:
                raise ToolExecutionError(
                    "status must be pending, approved, rejected, or cancelled"
                ) from exc
            rows = [r for r in rows if r.status == wanted]
        capped = rows[: args.limit]
        return ListMyLeaveRequestsOutput(
            count=len(capped),
            requests=[_my_request_summary(r) for r in capped],
        )


# --- get_my_leave_request ---


class GetMyLeaveRequestInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1, description="Own leave request ID.")


class GetMyLeaveRequestOutput(BaseModel):
    model_config = {"extra": "forbid"}

    request: MyLeaveRequestSummary


class GetMyLeaveRequestTool(BaseTool):
    name = "get_my_leave_request"
    description = (
        "Get one of the authenticated employee's leave requests by request_id. "
        "Does not accept employee_id. Read-only."
    )
    metadata = _SELF_META
    input_model = GetMyLeaveRequestInput
    output_model = GetMyLeaveRequestOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetMyLeaveRequestInput)
        _require_employee_id(context)
        request = _call_service(
            lambda: self._leave.get_request_for_user(context.user_id, args.request_id),
            error_message="Failed to load leave request",
        )
        return GetMyLeaveRequestOutput(request=_my_request_summary(request))


# --- get_my_work_status ---


class GetMyWorkStatusInput(BaseModel):
    model_config = {"extra": "forbid"}

    as_of: date | None = Field(
        default=None,
        description="Date to check (YYYY-MM-DD). Defaults to current UTC date.",
    )


class GetMyWorkStatusOutput(BaseModel):
    model_config = {"extra": "forbid"}

    as_of: date
    current_work_status: str
    leave_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class GetMyWorkStatusTool(BaseTool):
    name = "get_my_work_status"
    description = (
        "Return whether the authenticated employee is currently on leave "
        "(and leave type/dates if so). Does not accept employee_id. Read-only."
    )
    metadata = _SELF_META
    input_model = GetMyWorkStatusInput
    output_model = GetMyWorkStatusOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetMyWorkStatusInput)
        employee_id = _require_employee_id(context)
        day = args.as_of or datetime.now(UTC).date()
        payload = _call_service(
            lambda: self._leave.get_current_work_status(employee_id, as_of=day),
            error_message="Failed to load work status",
        )
        leave = payload.current_leave
        status = payload.current_work_status
        return GetMyWorkStatusOutput(
            as_of=day,
            current_work_status=(
                status.value if hasattr(status, "value") else str(status)
            ),
            leave_type=leave.leave_type if leave else None,
            start_date=leave.start_date if leave else None,
            end_date=leave.end_date if leave else None,
        )
