"""Training Agent write tools — confirmation-gated wrappers over TrainingService."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.training.schemas import OnboardingTrainingAssignRequest
from app.modules.training.service import TrainingService
from app.shared.exceptions import AppException

_SELF_WRITE_META = ToolMetadata(
    operation="write",
    required_permissions=frozenset(),
    operates_on_current_user=True,
    may_require_confirmation=True,
)

_HR_WRITE_META = ToolMetadata(
    operation="write",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"training:write"}),
    operates_on_current_user=False,
    may_require_confirmation=True,
)


def _call_service(fn, *, error_message: str):
    try:
        return fn()
    except AppException as exc:
        msg = (exc.message or "").strip() or error_message
        lowered = msg.lower()
        if any(
            token in lowered
            for token in ("sqlalchemy", "traceback", "psycopg", "operationalerror")
        ):
            raise ToolExecutionError(error_message) from exc
        raise ToolExecutionError(msg) from exc
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


# --- complete_my_training_assignment ---


class CompleteMyTrainingAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_assignment_id: int = Field(
        ge=1,
        description="Own onboarding training assignment id to mark completed.",
    )


class CompleteMyTrainingAssignmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "complete_my_training_assignment"
    training_assignment_id: int
    training_id: int
    onboarding_id: int
    status: str
    message: str


class CompleteMyTrainingAssignmentTool(BaseTool):
    name = "complete_my_training_assignment"
    description = (
        "Propose marking one of the authenticated employee's own onboarding training "
        "assignments as completed (training_assignment_id). Self-scoped only — does not "
        "accept employee_id, user_id, or onboarding_id. Requires confirmation. "
        "Write action — do not call for read-only questions."
    )
    metadata = _SELF_WRITE_META
    input_model = CompleteMyTrainingAssignmentInput
    output_model = CompleteMyTrainingAssignmentOutput

    def __init__(self, training_service: TrainingService) -> None:
        self._service = training_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CompleteMyTrainingAssignmentInput)
        _require_employee_id(context)
        assignment = _call_service(
            lambda: self._service.complete_assignment_for_user(
                context.user_id, args.training_assignment_id
            ),
            error_message="Unable to complete training assignment",
        )
        return CompleteMyTrainingAssignmentOutput(
            training_assignment_id=assignment.id,
            training_id=assignment.training_id,
            onboarding_id=assignment.onboarding_id,
            status=_enum_value(assignment.status),
            message="Training assignment marked completed.",
        )


# --- assign_training_to_onboarding ---


class AssignTrainingToOnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int = Field(ge=1, description="Onboarding record id.")
    training_id: int = Field(ge=1, description="Catalogue training id to assign.")


class AssignTrainingToOnboardingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "assign_training_to_onboarding"
    assignment_id: int
    onboarding_id: int
    training_id: int
    status: str
    message: str


class AssignTrainingToOnboardingTool(BaseTool):
    name = "assign_training_to_onboarding"
    description = (
        "Propose assigning an existing catalogue training (training_id) to an "
        "onboarding (onboarding_id). Requires HR/Admin staff role and training:write. "
        "Does not accept employee_id. Requires confirmation. Write action."
    )
    metadata = _HR_WRITE_META
    input_model = AssignTrainingToOnboardingInput
    output_model = AssignTrainingToOnboardingOutput

    def __init__(self, training_service: TrainingService) -> None:
        self._service = training_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, AssignTrainingToOnboardingInput)
        assignment = _call_service(
            lambda: self._service.assign_training(
                args.onboarding_id,
                OnboardingTrainingAssignRequest(training_id=args.training_id),
            ),
            error_message="Unable to assign training to onboarding",
        )
        return AssignTrainingToOnboardingOutput(
            assignment_id=assignment.id,
            onboarding_id=assignment.onboarding_id,
            training_id=assignment.training_id,
            status=_enum_value(assignment.status),
            message="Training assigned to onboarding.",
        )
