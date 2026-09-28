"""Training Agent read tools — wrap TrainingService only (no repositories / DB)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.training.service import TrainingService, build_assignment_response
from app.shared.exceptions import AppException

_SELF_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset(),
    operates_on_current_user=True,
)

_HR_META = ToolMetadata(
    operation="read",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"training:read"}),
    operates_on_current_user=False,
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


# --- Compact output shapes ---


class TrainingAssignmentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: int
    training_id: int
    title: str
    description: str | None = None
    resource_url: str | None = None
    status: str
    assigned_at: datetime
    completed_at: datetime | None = None


class TrainingBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_id: int
    title: str
    description: str | None = None
    resource_url: str | None = None


class OnboardingTrainingAssignmentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: int
    onboarding_id: int
    training_id: int
    title: str
    description: str | None = None
    resource_url: str | None = None
    status: str
    assigned_at: datetime
    completed_at: datetime | None = None


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainingAssignmentList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignments: list[TrainingAssignmentBrief] = Field(default_factory=list)


class TrainingList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trainings: list[TrainingBrief] = Field(default_factory=list)


class OnboardingTrainingAssignmentList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignments: list[OnboardingTrainingAssignmentBrief] = Field(default_factory=list)


def _assignment_brief(assignment) -> TrainingAssignmentBrief:
    resp = build_assignment_response(assignment)
    status = resp.status.value if hasattr(resp.status, "value") else str(resp.status)
    return TrainingAssignmentBrief(
        assignment_id=resp.id,
        training_id=resp.training_id,
        title=resp.title,
        description=resp.description,
        resource_url=resp.resource_url,
        status=status,
        assigned_at=resp.assigned_at,
        completed_at=resp.completed_at,
    )


def _onboarding_assignment_brief(assignment) -> OnboardingTrainingAssignmentBrief:
    resp = build_assignment_response(assignment)
    status = resp.status.value if hasattr(resp.status, "value") else str(resp.status)
    return OnboardingTrainingAssignmentBrief(
        assignment_id=resp.id,
        onboarding_id=resp.onboarding_id,
        training_id=resp.training_id,
        title=resp.title,
        description=resp.description,
        resource_url=resp.resource_url,
        status=status,
        assigned_at=resp.assigned_at,
        completed_at=resp.completed_at,
    )


def _training_brief(training) -> TrainingBrief:
    return TrainingBrief(
        training_id=training.id,
        title=training.title,
        description=training.description,
        resource_url=training.resource_url,
    )


# --- SELF ---


class ListMyTrainingAssignmentsTool(BaseTool):
    name = "list_my_training_assignments"
    description = (
        "List ONLY the authenticated caller's own onboarding training assignments "
        "(title, status, resource_url). Identity is taken from the session user_id — "
        "never accepts employee_id, onboarding_id, or user_id. "
        "Do not use this tool to look up another person."
    )
    metadata = _SELF_META
    input_model = EmptyInput
    output_model = TrainingAssignmentList

    def __init__(self, training_service: TrainingService) -> None:
        self._service = training_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, EmptyInput)
        # Authoritative identity: context.user_id only (TrainingService self path).
        rows = _call_service(
            lambda: self._service.list_assignments_for_user(context.user_id),
            error_message="Unable to load your training assignments",
        )
        return TrainingAssignmentList(assignments=[_assignment_brief(row) for row in rows])


# --- HR ---


class ListTrainingsTool(BaseTool):
    name = "list_trainings"
    description = (
        "List the company training catalogue (title, description, resource_url). "
        "Requires HR or Admin staff role AND training:read. "
        "Employees and managers cannot use this tool even if they have training:read."
    )
    metadata = _HR_META
    input_model = EmptyInput
    output_model = TrainingList

    def __init__(self, training_service: TrainingService) -> None:
        self._service = training_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, EmptyInput)
        rows = _call_service(
            lambda: self._service.list_trainings(),
            error_message="Unable to load training catalogue",
        )
        return TrainingList(trainings=[_training_brief(row) for row in rows])


class ListOnboardingTrainingAssignmentsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int = Field(ge=1)


class ListOnboardingTrainingAssignmentsTool(BaseTool):
    name = "list_onboarding_training_assignments"
    description = (
        "List training assignments for a specific onboarding_id "
        "(title, status, resource_url). Requires HR or Admin staff role AND training:read. "
        "onboarding_id is allowed only after that authorization. Does not accept employee_id. "
        "Employees and managers cannot use this tool even if they have training:read."
    )
    metadata = _HR_META
    input_model = ListOnboardingTrainingAssignmentsInput
    output_model = OnboardingTrainingAssignmentList

    def __init__(self, training_service: TrainingService) -> None:
        self._service = training_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListOnboardingTrainingAssignmentsInput)
        rows = _call_service(
            lambda: self._service.list_assignments_for_hr(args.onboarding_id),
            error_message="Unable to load onboarding training assignments",
        )
        return OnboardingTrainingAssignmentList(
            assignments=[_onboarding_assignment_brief(row) for row in rows]
        )
