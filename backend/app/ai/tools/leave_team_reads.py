"""Manager-scoped Leave Agent read tools (direct reports via org chart)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.leave.models import LeaveRequestStatus
from app.modules.leave.service import LeaveService, build_leave_request_response
from app.shared.exceptions import AppException

_TEAM_META = ToolMetadata(
    operation="read",
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


def _require_user_employee(context: AIExecutionContext) -> None:
    if context.employee_id is None:
        raise ToolExecutionError("No employee profile for the authenticated user")


class TeamLeaveBalanceItem(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int
    leave_type_name: str
    days_allowed: int
    days_used: int
    days_pending: int
    days_available: int


class TeamLeaveRequestSummary(BaseModel):
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


class DirectReportMatch(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    full_name: str
    email: str


class OnLeaveTeamItem(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int
    employee_id: int
    employee_name: str | None = None
    leave_type_name: str
    start_date: date
    end_date: date
    cancellation_status: str


def _request_summary(request) -> TeamLeaveRequestSummary:
    dto = build_leave_request_response(request)
    return TeamLeaveRequestSummary(
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
    )


def _parse_status(raw: str | None) -> LeaveRequestStatus | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return LeaveRequestStatus(str(raw).strip().lower())
    except ValueError as exc:
        raise ToolExecutionError(
            "status must be pending, approved, rejected, or cancelled"
        ) from exc


# --- find_direct_reports ---


class FindDirectReportsInput(BaseModel):
    model_config = {"extra": "forbid"}

    q: str | None = Field(
        default=None,
        max_length=120,
        description="Optional name/email substring among direct reports.",
    )
    limit: int = Field(default=20, ge=1, le=50)


class FindDirectReportsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    query: str | None
    count: int
    employees: list[DirectReportMatch]
    message: str | None = None


class FindDirectReportsTool(BaseTool):
    name = "find_direct_reports"
    description = (
        "Search the authenticated user's direct reports by name (org-chart only). "
        "If count is 0 or greater than 1, ask which employee_id to use; do not guess. "
        "Read-only."
    )
    metadata = _TEAM_META
    input_model = FindDirectReportsInput
    output_model = FindDirectReportsOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, FindDirectReportsInput)
        _require_user_employee(context)
        q = args.q.strip() if args.q else None
        rows = _call_service(
            lambda: self._leave.list_direct_reports_for_user(context.user_id, q=q),
            error_message="Failed to list direct reports",
        )
        matches = [
            DirectReportMatch(
                employee_id=emp.id,
                full_name=f"{emp.first_name} {emp.last_name}".strip(),
                email=emp.email or "",
            )
            for emp in rows[: args.limit]
        ]
        message = None
        if len(matches) == 0:
            message = (
                "No direct reports matched. Ask for a different name or employee_id, "
                "or confirm they report to you."
            )
        elif len(matches) > 1:
            message = (
                "Multiple direct reports matched. Ask which employee_id to use; "
                "do not pick one automatically."
            )
        return FindDirectReportsOutput(
            query=q,
            count=len(matches),
            employees=matches,
            message=message,
        )


# --- get_direct_report_leave_balance ---


class GetDirectReportLeaveBalanceInput(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int = Field(
        ge=1,
        description="Direct report employee_id from find_direct_reports.",
    )
    year: int | None = Field(default=None, ge=2000, le=2100)


class GetDirectReportLeaveBalanceOutput(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    year: int
    balances: list[TeamLeaveBalanceItem] = Field(default_factory=list)
    note: str = (
        "days_available is days_allowed minus days_used only; "
        "pending requests are listed separately."
    )


class GetDirectReportLeaveBalanceTool(BaseTool):
    name = "get_direct_report_leave_balance"
    description = (
        "Leave balances for a direct report only (org-chart). "
        "Denied for unrelated employees. Resolve name via find_direct_reports first. "
        "Read-only."
    )
    metadata = _TEAM_META
    input_model = GetDirectReportLeaveBalanceInput
    output_model = GetDirectReportLeaveBalanceOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetDirectReportLeaveBalanceInput)
        _require_user_employee(context)
        rows = _call_service(
            lambda: self._leave.get_balances_for_direct_report(
                context.user_id, args.employee_id, year=args.year
            ),
            error_message="Failed to retrieve leave balances",
        )
        if rows:
            year = rows[0].year
        elif args.year is not None:
            year = args.year
        else:
            year = datetime.now(UTC).year
        return GetDirectReportLeaveBalanceOutput(
            employee_id=args.employee_id,
            year=year,
            balances=[
                TeamLeaveBalanceItem(
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


# --- list_team_leave_requests ---


class ListTeamLeaveRequestsInput(BaseModel):
    model_config = {"extra": "forbid"}

    status: str | None = Field(
        default=None,
        description="pending | approved | rejected | cancelled",
    )
    limit: int = Field(default=50, ge=1, le=100)


class ListTeamLeaveRequestsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    count: int
    requests: list[TeamLeaveRequestSummary]


class ListTeamLeaveRequestsTool(BaseTool):
    name = "list_team_leave_requests"
    description = (
        "List leave requests for the authenticated user's direct reports only. "
        "Not organization-wide. Read-only."
    )
    metadata = _TEAM_META
    input_model = ListTeamLeaveRequestsInput
    output_model = ListTeamLeaveRequestsOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListTeamLeaveRequestsInput)
        _require_user_employee(context)
        status = _parse_status(args.status)
        rows = _call_service(
            lambda: self._leave.list_team_requests_for_user(
                context.user_id, status=status
            ),
            error_message="Failed to list team leave requests",
        )
        capped = rows[: args.limit]
        return ListTeamLeaveRequestsOutput(
            count=len(capped),
            requests=[_request_summary(r) for r in capped],
        )


# --- list_team_pending_leave_requests ---


class ListTeamPendingLeaveRequestsInput(BaseModel):
    model_config = {"extra": "forbid"}

    limit: int = Field(default=50, ge=1, le=100)


class ListTeamPendingLeaveRequestsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    count: int
    requests: list[TeamLeaveRequestSummary]


class ListTeamPendingLeaveRequestsTool(BaseTool):
    name = "list_team_pending_leave_requests"
    description = (
        "List pending leave requests for direct reports only (manager inbox). "
        "If the user asked to approve/reject and this returns exactly one request, "
        "next call approve_leave_request / reject_leave_request with that request_id "
        "so the UI Confirm button appears. Read-only."
    )
    metadata = _TEAM_META
    input_model = ListTeamPendingLeaveRequestsInput
    output_model = ListTeamPendingLeaveRequestsOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListTeamPendingLeaveRequestsInput)
        _require_user_employee(context)
        rows = _call_service(
            lambda: self._leave.list_team_requests_for_user(
                context.user_id, status=LeaveRequestStatus.PENDING
            ),
            error_message="Failed to list team pending leave requests",
        )
        capped = rows[: args.limit]
        return ListTeamPendingLeaveRequestsOutput(
            count=len(capped),
            requests=[_request_summary(r) for r in capped],
        )


# --- get_team_leave_request ---


class GetTeamLeaveRequestInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1)


class GetTeamLeaveRequestOutput(BaseModel):
    model_config = {"extra": "forbid"}

    request: TeamLeaveRequestSummary


class GetTeamLeaveRequestTool(BaseTool):
    name = "get_team_leave_request"
    description = (
        "Get one leave request belonging to a direct report. "
        "Unrelated employees' requests are not found. Read-only."
    )
    metadata = _TEAM_META
    input_model = GetTeamLeaveRequestInput
    output_model = GetTeamLeaveRequestOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetTeamLeaveRequestInput)
        _require_user_employee(context)
        request = _call_service(
            lambda: self._leave.get_request_for_team_member(
                context.user_id, args.request_id
            ),
            error_message="Failed to load leave request",
        )
        return GetTeamLeaveRequestOutput(request=_request_summary(request))


# --- list_team_currently_on_leave ---


class ListTeamCurrentlyOnLeaveInput(BaseModel):
    model_config = {"extra": "forbid"}

    as_of: date | None = Field(
        default=None,
        description="Date to check (YYYY-MM-DD). Defaults to current UTC date.",
    )


class ListTeamCurrentlyOnLeaveOutput(BaseModel):
    model_config = {"extra": "forbid"}

    as_of: date
    count: int
    items: list[OnLeaveTeamItem]


class ListTeamCurrentlyOnLeaveTool(BaseTool):
    name = "list_team_currently_on_leave"
    description = (
        "List direct reports currently on approved leave covering as_of. "
        "Not organization-wide. Read-only."
    )
    metadata = _TEAM_META
    input_model = ListTeamCurrentlyOnLeaveInput
    output_model = ListTeamCurrentlyOnLeaveOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListTeamCurrentlyOnLeaveInput)
        _require_user_employee(context)
        day = args.as_of or datetime.now(UTC).date()
        rows = _call_service(
            lambda: self._leave.list_currently_on_leave_for_team(
                context.user_id, as_of=day
            ),
            error_message="Failed to list team members on leave",
        )
        items: list[OnLeaveTeamItem] = []
        for request in rows:
            name = None
            if request.employee is not None:
                name = f"{request.employee.first_name} {request.employee.last_name}".strip()
            cancel = request.cancellation_status
            items.append(
                OnLeaveTeamItem(
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
        return ListTeamCurrentlyOnLeaveOutput(as_of=day, count=len(items), items=items)
