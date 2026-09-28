"""Onboarding Agent write tools — confirmation-gated wrappers over OnboardingService."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.onboarding.service import OnboardingService
from app.shared.exceptions import AppException

_ACK_META = ToolMetadata(
    operation="write",
    required_permissions=frozenset(),
    operates_on_current_user=True,
    may_require_confirmation=True,
)

_HR_WRITE_META = ToolMetadata(
    operation="write",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"onboarding:write"}),
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


def _require_employee_id(context: AIExecutionContext) -> int:
    if context.employee_id is None:
        raise ToolExecutionError("No employee profile for the authenticated user")
    return context.employee_id


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


# --- acknowledge_onboarding_task ---


class AcknowledgeOnboardingTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(ge=1, description="Acknowledgement task id to acknowledge.")


class AcknowledgeOnboardingTaskOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "acknowledge_onboarding_task"
    task_id: int
    onboarding_id: int
    status: str
    message: str


class AcknowledgeOnboardingTaskTool(BaseTool):
    name = "acknowledge_onboarding_task"
    description = (
        "Propose acknowledging one of the authenticated employee's acknowledgement-type "
        "onboarding tasks (task_id). Self-scoped only — does not accept employee_id. "
        "Only ACKNOWLEDGEMENT tasks are allowed; manual/document/training/profile tasks are rejected. "
        "Requires confirmation. Write action — do not call for read-only questions."
    )
    metadata = _ACK_META
    input_model = AcknowledgeOnboardingTaskInput
    output_model = AcknowledgeOnboardingTaskOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, AcknowledgeOnboardingTaskInput)
        _require_employee_id(context)
        task = _call_service(
            lambda: self._service.acknowledge_task_for_employee(
                context.user_id, args.task_id
            ),
            error_message="Unable to acknowledge onboarding task",
        )
        return AcknowledgeOnboardingTaskOutput(
            task_id=task.id,
            onboarding_id=task.onboarding_id,
            status=_enum_value(task.status),
            message="Acknowledgement task marked completed.",
        )


# --- complete_manual_onboarding_task ---


class CompleteManualOnboardingTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(ge=1, description="Manual onboarding task id.")


class CompleteManualOnboardingTaskOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "complete_manual_onboarding_task"
    task_id: int
    onboarding_id: int
    status: str
    message: str


class CompleteManualOnboardingTaskTool(BaseTool):
    name = "complete_manual_onboarding_task"
    description = (
        "Propose completing a MANUAL onboarding task for HR/Admin (task_id). "
        "Does not complete evidence-based tasks (profile, documents, training, etc.). "
        "Requires onboarding:write and confirmation. Write action."
    )
    metadata = _HR_WRITE_META
    input_model = CompleteManualOnboardingTaskInput
    output_model = CompleteManualOnboardingTaskOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CompleteManualOnboardingTaskInput)
        task = _call_service(
            lambda: self._service.complete_manual_task_for_hr(args.task_id),
            error_message="Unable to complete manual onboarding task",
        )
        return CompleteManualOnboardingTaskOutput(
            task_id=task.id,
            onboarding_id=task.onboarding_id,
            status=_enum_value(task.status),
            message="Manual onboarding task marked completed.",
        )


# --- complete_onboarding ---


class CompleteOnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int = Field(ge=1, description="Onboarding record id to force-complete.")


class CompleteOnboardingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "complete_onboarding"
    onboarding_id: int
    employee_id: int
    status: str
    message: str


class CompleteOnboardingTool(BaseTool):
    name = "complete_onboarding"
    description = (
        "Propose HR/Admin force-completion of an onboarding by onboarding_id. "
        "Does not change employment status or rewrite task history. "
        "Requires onboarding:write and confirmation. Write action."
    )
    metadata = _HR_WRITE_META
    input_model = CompleteOnboardingInput
    output_model = CompleteOnboardingOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CompleteOnboardingInput)
        onboarding = _call_service(
            lambda: self._service.complete_for_hr(args.onboarding_id),
            error_message="Unable to complete onboarding",
        )
        return CompleteOnboardingOutput(
            onboarding_id=onboarding.id,
            employee_id=onboarding.employee_id,
            status=_enum_value(onboarding.status),
            message="Onboarding marked completed.",
        )
