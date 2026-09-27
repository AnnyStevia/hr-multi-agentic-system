"""AI write tools wrapping LeaveService (confirmation-gated)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.leave.models import LeaveRequest
from app.modules.leave.schemas import LeaveRequestCreateRequest
from app.modules.leave.service import LeaveService
from app.shared.exceptions import AppException

_WRITE_META = ToolMetadata(
    operation="write",
    required_permissions=frozenset({"leaves:write"}),
    operates_on_current_user=False,
    may_require_confirmation=True,
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


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _compact_request(request: LeaveRequest) -> dict:
    leave_type_name = ""
    if getattr(request, "leave_type", None) is not None:
        leave_type_name = request.leave_type.name or ""
    return {
        "request_id": request.id,
        "employee_id": request.employee_id,
        "leave_type_id": request.leave_type_id,
        "leave_type_name": leave_type_name,
        "start_date": request.start_date.isoformat()
        if isinstance(request.start_date, date)
        else str(request.start_date),
        "end_date": request.end_date.isoformat()
        if isinstance(request.end_date, date)
        else str(request.end_date),
        "requested_days": request.requested_days,
        "status": _enum_value(request.status),
        "cancellation_status": _enum_value(request.cancellation_status),
        "manager_approval": _enum_value(request.manager_approval),
        "hr_approval": _enum_value(request.hr_approval),
    }


class LeaveRequestWriteOutput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int
    employee_id: int
    leave_type_id: int
    leave_type_name: str = ""
    start_date: str
    end_date: str
    requested_days: int
    status: str
    cancellation_status: str
    manager_approval: str
    hr_approval: str


# --- create_leave_request ---


class CreateLeaveRequestInput(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int | None = Field(
        default=None,
        ge=1,
        description="Leave type ID from list_leave_types or get_my_leave_balance.",
    )
    leave_type_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Leave type name (e.g. Annual Leave) if leave_type_id is unknown.",
    )
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _require_type(self):
        if self.leave_type_id is None and not (self.leave_type_name or "").strip():
            raise ValueError("Provide leave_type_id or leave_type_name")
        return self


class CreateLeaveRequestTool(BaseTool):
    name = "create_leave_request"
    description = (
        "Submit a leave request for the authenticated employee only. "
        "Pass leave_type_id or leave_type_name (e.g. 'Annual Leave'), plus start_date and end_date. "
        "Does not accept employee_id — never create leave on behalf of someone else. "
        "Requires confirmation. Write action."
    )
    metadata = _WRITE_META
    input_model = CreateLeaveRequestInput
    output_model = LeaveRequestWriteOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CreateLeaveRequestInput)
        leave_type_id = args.leave_type_id
        if leave_type_id is None:
            leave_type = _call_service(
                lambda: self._leave.get_type_by_name((args.leave_type_name or "").strip()),
                error_message="Failed to resolve leave type",
            )
            leave_type_id = leave_type.id
        payload = LeaveRequestCreateRequest(
            leave_type_id=leave_type_id,
            start_date=args.start_date,
            end_date=args.end_date,
            reason=args.reason,
        )
        request = _call_service(
            lambda: self._leave.create_request_for_user(context.user_id, payload),
            error_message="Failed to create leave request",
        )
        return LeaveRequestWriteOutput(**_compact_request(request))


# --- approve_leave_request ---


class ApproveLeaveRequestInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1)


class ApproveLeaveRequestTool(BaseTool):
    name = "approve_leave_request"
    description = (
        "Propose approval of a pending leave request (request_id). "
        "Call this when the user asks to approve and you know the request_id "
        "(e.g. after list_team_pending_leave_requests / list_pending_leave_requests). "
        "Returns pending_confirmation for the UI Confirm button — does not approve until confirmed. "
        "Do not only describe the request in text. Authorization is enforced by LeaveService."
    )
    metadata = _WRITE_META
    input_model = ApproveLeaveRequestInput
    output_model = LeaveRequestWriteOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ApproveLeaveRequestInput)
        request = _call_service(
            lambda: self._leave.approve_request(args.request_id, context.user_id),
            error_message="Failed to approve leave request",
        )
        return LeaveRequestWriteOutput(**_compact_request(request))


# --- reject_leave_request ---


class RejectLeaveRequestInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1)
    rejection_reason: str = Field(min_length=1, max_length=2000)


class RejectLeaveRequestTool(BaseTool):
    name = "reject_leave_request"
    description = (
        "Propose rejection of a pending leave request (request_id + rejection_reason). "
        "Call this when the user asks to reject and you know the request_id. "
        "Returns pending_confirmation for the UI Confirm button — does not reject until confirmed. "
        "Authorization is enforced by LeaveService."
    )
    metadata = _WRITE_META
    input_model = RejectLeaveRequestInput
    output_model = LeaveRequestWriteOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, RejectLeaveRequestInput)
        request = _call_service(
            lambda: self._leave.reject_request(
                args.request_id, context.user_id, args.rejection_reason
            ),
            error_message="Failed to reject leave request",
        )
        return LeaveRequestWriteOutput(**_compact_request(request))


# --- cancel_pending_leave_request ---


class CancelPendingLeaveRequestInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1)


class CancelPendingLeaveRequestTool(BaseTool):
    name = "cancel_pending_leave_request"
    description = (
        "Cancel the authenticated employee's own pending leave request. "
        "Requires confirmation. Write action."
    )
    metadata = _WRITE_META
    input_model = CancelPendingLeaveRequestInput
    output_model = LeaveRequestWriteOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CancelPendingLeaveRequestInput)
        request = _call_service(
            lambda: self._leave.cancel_request_for_user(
                context.user_id, args.request_id
            ),
            error_message="Failed to cancel pending leave request",
        )
        return LeaveRequestWriteOutput(**_compact_request(request))


# --- request_leave_cancellation ---


class RequestLeaveCancellationInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


class RequestLeaveCancellationTool(BaseTool):
    name = "request_leave_cancellation"
    description = (
        "Request cancellation of the authenticated employee's own future approved leave. "
        "Does not cancel immediately — sets cancellation_status=requested. "
        "Requires confirmation. Write action."
    )
    metadata = _WRITE_META
    input_model = RequestLeaveCancellationInput
    output_model = LeaveRequestWriteOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, RequestLeaveCancellationInput)
        request = _call_service(
            lambda: self._leave.request_cancellation_for_user(
                context.user_id, args.request_id, args.reason
            ),
            error_message="Failed to request leave cancellation",
        )
        return LeaveRequestWriteOutput(**_compact_request(request))


# --- approve_leave_cancellation ---


class ApproveLeaveCancellationInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1)


class ApproveLeaveCancellationTool(BaseTool):
    name = "approve_leave_cancellation"
    description = (
        "Approve a pending leave cancellation request as the authenticated reviewer. "
        "Authorization is enforced by LeaveService. Requires confirmation. Write action."
    )
    metadata = _WRITE_META
    input_model = ApproveLeaveCancellationInput
    output_model = LeaveRequestWriteOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ApproveLeaveCancellationInput)
        request = _call_service(
            lambda: self._leave.approve_cancellation(args.request_id, context.user_id),
            error_message="Failed to approve leave cancellation",
        )
        return LeaveRequestWriteOutput(**_compact_request(request))


# --- reject_leave_cancellation ---


class RejectLeaveCancellationInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: int = Field(ge=1)
    rejection_reason: str = Field(min_length=1, max_length=2000)


class RejectLeaveCancellationTool(BaseTool):
    name = "reject_leave_cancellation"
    description = (
        "Reject a pending leave cancellation request as the authenticated reviewer. "
        "Authorization is enforced by LeaveService. Requires confirmation. Write action."
    )
    metadata = _WRITE_META
    input_model = RejectLeaveCancellationInput
    output_model = LeaveRequestWriteOutput

    def __init__(self, leave_service: LeaveService):
        self._leave = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, RejectLeaveCancellationInput)
        request = _call_service(
            lambda: self._leave.reject_cancellation(
                args.request_id, context.user_id, args.rejection_reason
            ),
            error_message="Failed to reject leave cancellation",
        )
        return LeaveRequestWriteOutput(**_compact_request(request))
