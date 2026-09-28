"""Onboarding Agent read tools — wrap OnboardingService only (no repositories / DB)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.onboarding.service import (
    OnboardingService,
    build_onboarding_response,
    build_onboarding_task_response,
    build_template_response,
)
from app.shared.exceptions import AppException

_SELF_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset(),
    operates_on_current_user=True,
)

_HR_META = ToolMetadata(
    operation="read",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"onboarding:read"}),
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


def _require_employee_id(context: AIExecutionContext) -> int:
    """SELF tools require an employee profile; never fall back to user-supplied ids."""
    if context.employee_id is None:
        raise ToolExecutionError("No employee profile for the authenticated user")
    return context.employee_id


# --- Compact output shapes ---


class OnboardingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int
    employee_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None = None


class OnboardingListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int
    employee_id: int
    employee_name: str
    position: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    completed_tasks_count: int
    total_tasks_count: int


class ProgressCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    completed: int
    pending: int


class OnboardingProgressSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int
    status: str
    completed_at: datetime | None = None
    tasks: ProgressCount
    required_tasks: ProgressCount
    optional_tasks: ProgressCount
    trainings: ProgressCount
    documents_total: int
    overall_percentage: int


class OnboardingTaskSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int
    onboarding_id: int
    title: str
    description: str | None = None
    task_type: str
    is_required: bool
    status: str
    due_date: date | None = None
    completed_at: datetime | None = None
    document_type: str | None = None
    training_id: int | None = None


class OnboardingTemplateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: int
    title: str
    description: str | None = None
    task_type: str
    is_required: bool
    is_active: bool
    document_type: str | None = None
    training_id: int | None = None


def _progress_from_domain(progress) -> OnboardingProgressSummary:
    return OnboardingProgressSummary(
        onboarding_id=progress.onboarding_id,
        status=progress.status.value
        if hasattr(progress.status, "value")
        else str(progress.status),
        completed_at=progress.completed_at,
        tasks=ProgressCount(
            total=progress.tasks.total,
            completed=progress.tasks.completed,
            pending=progress.tasks.pending,
        ),
        required_tasks=ProgressCount(
            total=progress.required_tasks.total,
            completed=progress.required_tasks.completed,
            pending=progress.required_tasks.pending,
        ),
        optional_tasks=ProgressCount(
            total=progress.optional_tasks.total,
            completed=progress.optional_tasks.completed,
            pending=progress.optional_tasks.pending,
        ),
        trainings=ProgressCount(
            total=progress.trainings.total,
            completed=progress.trainings.completed,
            pending=progress.trainings.pending,
        ),
        documents_total=progress.documents.total,
        overall_percentage=progress.overall_percentage,
    )


def _task_from_domain(task) -> OnboardingTaskSummary:
    resp = build_onboarding_task_response(task)
    return OnboardingTaskSummary(
        task_id=resp.id,
        onboarding_id=resp.onboarding_id,
        title=resp.title,
        description=resp.description,
        task_type=resp.task_type.value
        if hasattr(resp.task_type, "value")
        else str(resp.task_type),
        is_required=resp.is_required,
        status=resp.status.value if hasattr(resp.status, "value") else str(resp.status),
        due_date=resp.due_date,
        completed_at=resp.completed_at,
        document_type=resp.document_type.value
        if resp.document_type is not None and hasattr(resp.document_type, "value")
        else (str(resp.document_type) if resp.document_type else None),
        training_id=resp.training_id,
    )


def _onboarding_from_domain(onboarding) -> OnboardingSummary:
    resp = build_onboarding_response(onboarding)
    return OnboardingSummary(
        onboarding_id=resp.id,
        employee_id=resp.employee_id,
        status=resp.status.value if hasattr(resp.status, "value") else str(resp.status),
        started_at=resp.started_at,
        completed_at=resp.completed_at,
    )


# --- SELF tools ---


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetMyOnboardingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding: OnboardingSummary


class GetMyOnboardingTool(BaseTool):
    name = "get_my_onboarding"
    description = (
        "Get the authenticated employee's own onboarding record (status, dates). "
        "Self-scoped only — never accepts another employee_id."
    )
    metadata = _SELF_META
    input_model = EmptyInput
    output_model = GetMyOnboardingOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        _require_employee_id(context)
        onboarding = _call_service(
            lambda: self._service.get_for_employee_user(context.user_id),
            error_message="Unable to load your onboarding",
        )
        return GetMyOnboardingOutput(onboarding=_onboarding_from_domain(onboarding))


class GetMyOnboardingProgressOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress: OnboardingProgressSummary


class GetMyOnboardingProgressTool(BaseTool):
    name = "get_my_onboarding_progress"
    description = (
        "Get the authenticated employee's onboarding progress percentages and task counts. "
        "Self-scoped only."
    )
    metadata = _SELF_META
    input_model = EmptyInput
    output_model = GetMyOnboardingProgressOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        _require_employee_id(context)
        progress = _call_service(
            lambda: self._service.get_progress_for_employee_user(context.user_id),
            error_message="Unable to load your onboarding progress",
        )
        return GetMyOnboardingProgressOutput(progress=_progress_from_domain(progress))


class ListMyOnboardingTasksOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[OnboardingTaskSummary]
    count: int


class ListMyOnboardingTasksTool(BaseTool):
    name = "list_my_onboarding_tasks"
    description = (
        "List the authenticated employee's onboarding tasks (title, type, required, status). "
        "Self-scoped only."
    )
    metadata = _SELF_META
    input_model = EmptyInput
    output_model = ListMyOnboardingTasksOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        _require_employee_id(context)
        tasks = _call_service(
            lambda: self._service.list_tasks_for_employee_user(context.user_id),
            error_message="Unable to list your onboarding tasks",
        )
        summaries = [_task_from_domain(t) for t in tasks]
        return ListMyOnboardingTasksOutput(tasks=summaries, count=len(summaries))


# --- HR tools ---


class ListOnboardingsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OnboardingListItem]
    count: int


class ListOnboardingsTool(BaseTool):
    name = "list_onboardings"
    description = (
        "List all employee onboardings for HR (status, employee name, task counts). "
        "Requires HR/Admin and onboarding:read."
    )
    metadata = _HR_META
    input_model = EmptyInput
    output_model = ListOnboardingsOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        items = _call_service(
            lambda: self._service.list_for_hr(),
            error_message="Unable to list onboardings",
        )
        mapped = [
            OnboardingListItem(
                onboarding_id=item.id,
                employee_id=item.employee_id,
                employee_name=item.employee_name,
                position=item.position,
                status=item.status.value
                if hasattr(item.status, "value")
                else str(item.status),
                started_at=item.started_at,
                completed_at=item.completed_at,
                completed_tasks_count=item.completed_tasks_count,
                total_tasks_count=item.total_tasks_count,
            )
            for item in items
        ]
        return ListOnboardingsOutput(items=mapped, count=len(mapped))


class GetOnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int = Field(ge=1, description="Onboarding record id.")


class GetOnboardingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding: OnboardingSummary


class GetOnboardingTool(BaseTool):
    name = "get_onboarding"
    description = (
        "Get an onboarding record by onboarding_id (HR). "
        "Requires HR/Admin and onboarding:read."
    )
    metadata = _HR_META
    input_model = GetOnboardingInput
    output_model = GetOnboardingOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetOnboardingInput)
        onboarding = _call_service(
            lambda: self._service.get_for_hr(args.onboarding_id),
            error_message="Unable to load onboarding",
        )
        return GetOnboardingOutput(onboarding=_onboarding_from_domain(onboarding))


class GetOnboardingByEmployeeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: int = Field(
        ge=1,
        description="Employee ID from find_employees (do not invent).",
    )


class GetOnboardingByEmployeeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding: OnboardingSummary


class GetOnboardingByEmployeeTool(BaseTool):
    name = "get_onboarding_by_employee"
    description = (
        "Get an employee's onboarding by employee_id (HR). "
        "Resolve names with find_employees first when needed. "
        "Requires HR/Admin and onboarding:read."
    )
    metadata = _HR_META
    input_model = GetOnboardingByEmployeeInput
    output_model = GetOnboardingByEmployeeOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetOnboardingByEmployeeInput)
        onboarding = _call_service(
            lambda: self._service.get_by_employee_id_for_hr(args.employee_id),
            error_message="Unable to load employee onboarding",
        )
        return GetOnboardingByEmployeeOutput(
            onboarding=_onboarding_from_domain(onboarding)
        )


class GetOnboardingProgressInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int = Field(ge=1, description="Onboarding record id.")


class GetOnboardingProgressOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress: OnboardingProgressSummary


class GetOnboardingProgressTool(BaseTool):
    name = "get_onboarding_progress"
    description = (
        "Get progress for an onboarding by onboarding_id (HR). "
        "Requires HR/Admin and onboarding:read."
    )
    metadata = _HR_META
    input_model = GetOnboardingProgressInput
    output_model = GetOnboardingProgressOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetOnboardingProgressInput)
        progress = _call_service(
            lambda: self._service.get_progress_for_hr(args.onboarding_id),
            error_message="Unable to load onboarding progress",
        )
        return GetOnboardingProgressOutput(progress=_progress_from_domain(progress))


class ListOnboardingTasksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_id: int = Field(ge=1, description="Onboarding record id.")


class ListOnboardingTasksOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[OnboardingTaskSummary]
    count: int


class ListOnboardingTasksTool(BaseTool):
    name = "list_onboarding_tasks"
    description = (
        "List tasks for an onboarding by onboarding_id (HR). "
        "Requires HR/Admin and onboarding:read."
    )
    metadata = _HR_META
    input_model = ListOnboardingTasksInput
    output_model = ListOnboardingTasksOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListOnboardingTasksInput)
        tasks = _call_service(
            lambda: self._service.list_tasks_for_hr(args.onboarding_id),
            error_message="Unable to list onboarding tasks",
        )
        summaries = [_task_from_domain(t) for t in tasks]
        return ListOnboardingTasksOutput(tasks=summaries, count=len(summaries))


class ListOnboardingTemplatesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_only: bool = Field(
        default=False,
        description="If true, return only active templates.",
    )


class ListOnboardingTemplatesOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    templates: list[OnboardingTemplateSummary]
    count: int


class ListOnboardingTemplatesTool(BaseTool):
    name = "list_onboarding_templates"
    description = (
        "List onboarding task templates/catalogue (HR). "
        "Requires HR/Admin and onboarding:read."
    )
    metadata = _HR_META
    input_model = ListOnboardingTemplatesInput
    output_model = ListOnboardingTemplatesOutput

    def __init__(self, onboarding_service: OnboardingService) -> None:
        self._service = onboarding_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListOnboardingTemplatesInput)
        templates = _call_service(
            lambda: self._service.list_templates(active_only=args.active_only),
            error_message="Unable to list onboarding templates",
        )
        mapped = []
        for template in templates:
            resp = build_template_response(template)
            mapped.append(
                OnboardingTemplateSummary(
                    template_id=resp.id,
                    title=resp.title,
                    description=resp.description,
                    task_type=resp.task_type.value
                    if hasattr(resp.task_type, "value")
                    else str(resp.task_type),
                    is_required=resp.is_required,
                    is_active=resp.is_active,
                    document_type=resp.document_type.value
                    if resp.document_type is not None
                    and hasattr(resp.document_type, "value")
                    else (str(resp.document_type) if resp.document_type else None),
                    training_id=resp.training_id,
                )
            )
        return ListOnboardingTemplatesOutput(templates=mapped, count=len(mapped))
