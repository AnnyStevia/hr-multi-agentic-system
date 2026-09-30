"""Offboarding Agent write tools — confirmation-gated wrappers over OffboardingService."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.identity.models import User
from app.modules.offboarding.models import OffboardingClearanceStatus
from app.modules.offboarding.schemas import OffboardingClearanceUpdateRequest
from app.modules.offboarding.service import OffboardingService
from app.shared.exceptions import AppException

_HR_WRITE_META = ToolMetadata(
    operation="write",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"offboarding:write"}),
    operates_on_current_user=False,
    may_require_confirmation=True,
)

# Dual-style: authorize any authenticated caller; execute() enforces HR vs self.
_DUAL_WRITE_META = ToolMetadata(
    operation="write",
    required_permissions=frozenset(),
    operates_on_current_user=False,
    may_require_confirmation=True,
)

_GENERIC_DENY = "Not authorized to execute this tool"


def _call_service(fn, *, error_message: str):
    try:
        return fn()
    except AppException as exc:
        raise ToolExecutionError(exc.message) from exc
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(error_message) from exc


def _is_hr_writer(context: AIExecutionContext) -> bool:
    return context.has_any_role("hr", "admin") and (
        "offboarding:write" in context.permission_names
    )


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _require_actor(get_user: Callable[[int], User | None], context: AIExecutionContext) -> User:
    user = get_user(context.user_id)
    if user is None:
        raise ToolExecutionError("Authenticated user not found")
    return user


# --- complete_offboarding_case ---


class CompleteOffboardingCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int = Field(ge=1, description="Offboarding case id to complete.")


class CompleteOffboardingCaseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "complete_offboarding_case"
    case_id: int
    employee_id: int
    status: str
    employment_status: str | None = None
    account_deactivated: bool = False
    message: str


class CompleteOffboardingCaseTool(BaseTool):
    name = "complete_offboarding_case"
    description = (
        "Propose completing an offboarding case (case_id) when O.5 readiness passes. "
        "HR/Admin + offboarding:write only. On success the domain marks the case "
        "completed and deactivates the employee's account/employment. Requires "
        "confirmation. Do not call for readiness questions — use get_offboarding_readiness."
    )
    metadata = _HR_WRITE_META
    input_model = CompleteOffboardingCaseInput
    output_model = CompleteOffboardingCaseOutput

    def __init__(self, service: OffboardingService) -> None:
        self._service = service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CompleteOffboardingCaseInput)
        case = _call_service(
            lambda: self._service.complete(args.case_id),
            error_message="Unable to complete offboarding case",
        )
        employee = case.employee
        employment_status = None
        account_deactivated = False
        if employee is not None:
            employment_status = _enum_value(employee.employment_status)
            account_deactivated = employee.user_id is not None
        return CompleteOffboardingCaseOutput(
            case_id=case.id,
            employee_id=case.employee_id,
            status=_enum_value(case.status),
            employment_status=employment_status,
            account_deactivated=account_deactivated,
            message="Offboarding case completed.",
        )


# --- update_offboarding_clearance ---


class UpdateOffboardingClearanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int = Field(ge=1, description="Offboarding case id.")
    item_id: int = Field(ge=1, description="Clearance item id.")
    status: Literal["cleared", "not_applicable", "pending"] = Field(
        description="New clearance status: cleared, not_applicable, or pending."
    )
    notes: str | None = Field(default=None, max_length=2000)


class UpdateOffboardingClearanceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "update_offboarding_clearance"
    case_id: int
    item_id: int
    item: str
    status: str
    message: str


class UpdateOffboardingClearanceTool(BaseTool):
    name = "update_offboarding_clearance"
    description = (
        "Propose updating a clearance item status (cleared / not_applicable / pending) "
        "for an offboarding case. HR/Admin + offboarding:write only. Employees cannot "
        "clear their own equipment via AI. Requires confirmation. "
        "completed_by / completed_at are set by the domain service."
    )
    metadata = _HR_WRITE_META
    input_model = UpdateOffboardingClearanceInput
    output_model = UpdateOffboardingClearanceOutput

    def __init__(
        self,
        service: OffboardingService,
        get_user: Callable[[int], User | None],
    ) -> None:
        self._service = service
        self._get_user = get_user

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, UpdateOffboardingClearanceInput)
        actor = _require_actor(self._get_user, context)
        status = OffboardingClearanceStatus(args.status)
        payload = OffboardingClearanceUpdateRequest(status=status, notes=args.notes)
        item = _call_service(
            lambda: self._service.update_clearance_item_for_hr(
                args.case_id, args.item_id, payload, actor
            ),
            error_message="Unable to update offboarding clearance item",
        )
        return UpdateOffboardingClearanceOutput(
            case_id=args.case_id,
            item_id=item.id,
            item=item.item,
            status=_enum_value(item.status),
            message=f"Clearance item marked {_enum_value(item.status)}.",
        )


# --- update_offboarding_task ---


class UpdateOffboardingTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["start", "complete", "reopen"] = Field(
        description="Task mutation: start, complete, or reopen (HR-only)."
    )
    task_id: int = Field(ge=1, description="Offboarding task id.")
    case_id: int | None = Field(
        default=None,
        ge=1,
        description="Required for HR operations; omit for employee self-assigned tasks.",
    )


class UpdateOffboardingTaskOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "update_offboarding_task"
    operation: str
    case_id: int
    task_id: int
    status: str
    message: str


class UpdateOffboardingTaskTool(BaseTool):
    name = "update_offboarding_task"
    description = (
        "Propose starting, completing, or reopening an offboarding checklist task. "
        "Employees may only start/complete tasks already assigned to them (no reopen). "
        "HR/Admin may start/complete/reopen with case_id + task_id. Requires confirmation. "
        "Skip is not available via AI."
    )
    metadata = _DUAL_WRITE_META
    input_model = UpdateOffboardingTaskInput
    output_model = UpdateOffboardingTaskOutput

    def __init__(
        self,
        service: OffboardingService,
        get_user: Callable[[int], User | None],
    ) -> None:
        self._service = service
        self._get_user = get_user

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, UpdateOffboardingTaskInput)
        if _is_hr_writer(context):
            if args.case_id is None:
                raise ToolExecutionError("case_id is required for HR task updates")
            case_id = args.case_id
            if args.operation == "start":
                task = _call_service(
                    lambda: self._service.start_task_for_hr(case_id, args.task_id),
                    error_message="Unable to start offboarding task",
                )
            elif args.operation == "complete":
                actor = _require_actor(self._get_user, context)
                task = _call_service(
                    lambda: self._service.complete_task_for_hr(
                        case_id, args.task_id, actor
                    ),
                    error_message="Unable to complete offboarding task",
                )
            else:
                task = _call_service(
                    lambda: self._service.reopen_task_for_hr(case_id, args.task_id),
                    error_message="Unable to reopen offboarding task",
                )
        else:
            if context.employee_id is None:
                raise ToolExecutionError(_GENERIC_DENY)
            if args.operation == "reopen":
                raise ToolExecutionError(_GENERIC_DENY)
            if args.operation == "start":
                task = _call_service(
                    lambda: self._service.start_task_for_user(
                        context.user_id, args.task_id
                    ),
                    error_message="Unable to start offboarding task",
                )
            else:
                actor = _require_actor(self._get_user, context)
                task = _call_service(
                    lambda: self._service.complete_task_for_user(
                        context.user_id, args.task_id, actor
                    ),
                    error_message="Unable to complete offboarding task",
                )

        return UpdateOffboardingTaskOutput(
            operation=args.operation,
            case_id=task.offboarding_case_id,
            task_id=task.id,
            status=_enum_value(task.status),
            message=f"Task {args.operation} succeeded.",
        )
