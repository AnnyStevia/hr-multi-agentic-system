"""Offboarding Agent read tools — wrap OffboardingService / EmployeeService only."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.employees.service import EmployeeService
from app.modules.offboarding.models import (
    ACTIVE_OFFBOARDING_STATUSES,
    OffboardingCase,
    OffboardingStatus,
)
from app.modules.offboarding.service import (
    OffboardingService,
    build_detail_response,
    build_employee_clearance_response,
    build_employee_exit_interview_response,
    build_employee_task_response,
    build_employee_view_response,
    build_exit_interview_response,
    build_task_response,
)
from app.shared.exceptions import AppException

# Dual-mode tools: authorize_tool allows any authenticated caller; execute() enforces
# HR (offboarding:read + hr/admin) vs self (employee_id in context).
_DUAL_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset(),
    operates_on_current_user=False,
)

_HR_META = ToolMetadata(
    operation="read",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"offboarding:read"}),
    operates_on_current_user=False,
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


def _is_hr(context: AIExecutionContext) -> bool:
    return context.has_any_role("hr", "admin") and (
        "offboarding:read" in context.permission_names
    )


def _require_hr(context: AIExecutionContext) -> None:
    if not _is_hr(context):
        raise ToolExecutionError(_GENERIC_DENY)


def _require_employee_profile(context: AIExecutionContext) -> int:
    if context.employee_id is None:
        raise ToolExecutionError("No employee profile for the authenticated user")
    return context.employee_id


def _status_value(status) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _pick_preferred_case(cases: list[OffboardingCase]) -> OffboardingCase | None:
    if not cases:
        return None
    for case in cases:
        if case.status in ACTIVE_OFFBOARDING_STATUSES:
            return case
    return cases[0]


def _own_cases(service: OffboardingService, user_id: int) -> list[OffboardingCase]:
    return _call_service(
        lambda: service.list_for_user(user_id),
        error_message="Failed to load offboarding cases",
    )


def _require_own_case_id(
    service: OffboardingService, context: AIExecutionContext, case_id: int
) -> OffboardingCase:
    _require_employee_profile(context)
    cases = _own_cases(service, context.user_id)
    for case in cases:
        if case.id == case_id:
            return case
    raise ToolExecutionError("Offboarding case not found")


def _resolve_self_case(
    service: OffboardingService,
    context: AIExecutionContext,
    case_id: int | None,
) -> OffboardingCase:
    _require_employee_profile(context)
    if case_id is not None:
        return _require_own_case_id(service, context, case_id)
    cases = _own_cases(service, context.user_id)
    case = _pick_preferred_case(cases)
    if case is None:
        raise ToolExecutionError("No offboarding case found for this employee")
    return case


def _resolve_hr_case(
    service: OffboardingService,
    *,
    case_id: int | None,
    employee_id: int | None,
) -> OffboardingCase:
    if case_id is not None:
        return _call_service(
            lambda: service.get_for_hr(case_id),
            error_message="Failed to load offboarding case",
        )
    if employee_id is not None:
        items = _call_service(
            lambda: service.list_for_hr(employee_id=employee_id),
            error_message="Failed to list offboarding cases",
        )
        if not items:
            raise ToolExecutionError("No offboarding case found for this employee")
        # Prefer active; list is newest-first — load full case for preferred id.
        preferred_id = items[0].id
        for item in items:
            if _status_value(item.status) in {
                s.value for s in ACTIVE_OFFBOARDING_STATUSES
            }:
                preferred_id = item.id
                break
        return _call_service(
            lambda: service.get_for_hr(preferred_id),
            error_message="Failed to load offboarding case",
        )
    raise ToolExecutionError("Provide case_id or employee_id")


def _should_use_hr_lookup(
    context: AIExecutionContext,
    *,
    case_id: int | None,
    employee_id: int | None,
) -> bool:
    """HR lookup only when a target id is explicit.

    Staff asking 'my offboarding…' with no ids use session employee_id (self path).
    """
    return _is_hr(context) and (case_id is not None or employee_id is not None)


def _resolve_dual_mode_case(
    service: OffboardingService,
    context: AIExecutionContext,
    *,
    case_id: int | None,
    employee_id: int | None,
) -> tuple[OffboardingCase, bool]:
    """Return (case, use_hr_view). Self when no target ids; HR view when ids given."""
    if _should_use_hr_lookup(context, case_id=case_id, employee_id=employee_id):
        return (
            _resolve_hr_case(service, case_id=case_id, employee_id=employee_id),
            True,
        )
    if context.employee_id is not None:
        return _resolve_self_case(service, context, case_id), False
    if _is_hr(context):
        raise ToolExecutionError(
            "Provide case_id or employee_id for the offboarding case to look up"
        )
    raise ToolExecutionError("No employee profile for the authenticated user")


def _readiness_for_case(
    service: OffboardingService, case: OffboardingCase
) -> "OffboardingReadinessResult":
    status = _status_value(case.status)
    if case.status in (OffboardingStatus.COMPLETED, OffboardingStatus.CANCELLED):
        return OffboardingReadinessResult(
            offboarding_case_id=case.id,
            ready=False,
            terminal=True,
            status=status,
            blockers=[],
        )
    can_complete, blockers = _call_service(
        lambda: service.can_complete(case.id),
        error_message="Failed to evaluate offboarding readiness",
    )
    return OffboardingReadinessResult(
        offboarding_case_id=case.id,
        ready=can_complete,
        terminal=False,
        status=status,
        blockers=list(blockers),
    )


# --- Compact schemas ---


class OffboardingCaseBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int
    employee_id: int | None = None
    employee_name: str | None = None
    reason: str
    reason_details: str | None = None
    last_working_day: date
    status: str
    initiated_at: datetime
    completed_at: datetime | None = None


class ChecklistProgressBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    skipped_tasks: int
    required_total: int
    required_completed: int
    percentage: int
    required_complete: bool


class ClearanceProgressBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    pending: int
    cleared: int
    not_applicable: int
    percentage: int
    clearance_complete: bool


class ExitInterviewStatusBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool
    status: str | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None


class OffboardingProgressAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int
    case_status: str
    checklist: ChecklistProgressBrief
    clearance: ClearanceProgressBrief
    exit_interview: ExitInterviewStatusBrief
    ready_to_complete: bool
    terminal: bool
    blockers: list[str] = Field(default_factory=list)


class OffboardingTaskBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int
    title: str
    category: str
    status: str
    is_required: bool
    assignee_name: str | None = None
    due_date: date | None = None
    completed_at: datetime | None = None


class OffboardingTaskListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[OffboardingTaskBrief]


class OffboardingClearanceItemBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int
    category: str
    item: str
    status: str
    notes: str | None = None
    completed_at: datetime | None = None


class OffboardingClearanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int | None = None
    items: list[OffboardingClearanceItemBrief]
    progress: ClearanceProgressBrief | None = None


class ExitInterviewBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_interview_id: int
    case_id: int
    status: str
    interviewer_name: str | None = None
    scheduled_at: datetime
    ends_at: datetime
    meeting_url: str | None = None
    meeting_available: bool
    feedback: str | None = None
    completed_at: datetime | None = None


class OffboardingReadinessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offboarding_case_id: int
    ready: bool
    terminal: bool
    status: str
    blockers: list[str] = Field(default_factory=list)


class OffboardingEmployeeMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: int
    full_name: str
    email: str
    position: str | None = None
    department: str | None = None
    status: str


class FindEmployeesForOffboardingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    count: int
    employees: list[OffboardingEmployeeMatch]
    message: str | None = None


# --- Inputs ---


class GetOffboardingCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int | None = None
    employee_id: int | None = None


class CaseScopedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int | None = None
    employee_id: int | None = None


class ListOffboardingTasksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int | None = None
    employee_id: int | None = None
    status: str | None = Field(
        default=None,
        description="Optional task status filter (pending, in_progress, completed, skipped)",
    )


class FindEmployeesForOffboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=20, ge=1, le=50)


# --- Tools ---


class GetOffboardingCaseTool(BaseTool):
    name = "get_offboarding_case"
    description = (
        "Get an offboarding case summary (status, reason, last working day, dates). "
        "For 'my/own' status: omit case_id and employee_id — uses the logged-in "
        "employee profile. HR looking up someone else: pass case_id or employee_id. "
        "Read-only."
    )
    metadata = _DUAL_META
    input_model = GetOffboardingCaseInput
    output_model = OffboardingCaseBrief

    def __init__(self, service: OffboardingService):
        self._service = service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetOffboardingCaseInput)
        case, use_hr_view = _resolve_dual_mode_case(
            self._service,
            context,
            case_id=args.case_id,
            employee_id=args.employee_id,
        )
        if use_hr_view:
            detail = build_detail_response(case)
            return OffboardingCaseBrief(
                case_id=detail.id,
                employee_id=detail.employee_id,
                employee_name=detail.employee.full_name,
                reason=_status_value(detail.reason),
                reason_details=detail.reason_details,
                last_working_day=detail.last_working_day,
                status=_status_value(detail.status),
                initiated_at=detail.initiated_at,
                completed_at=detail.completed_at,
            )

        view = build_employee_view_response(case)
        return OffboardingCaseBrief(
            case_id=view.id,
            employee_id=context.employee_id,
            employee_name=None,
            reason=_status_value(view.reason),
            reason_details=None,
            last_working_day=view.last_working_day,
            status=_status_value(view.status),
            initiated_at=view.initiated_at,
            completed_at=view.completed_at,
        )


class GetOffboardingProgressTool(BaseTool):
    name = "get_offboarding_progress"
    description = (
        "Aggregated offboarding progress: checklist, clearance, exit interview status, "
        "and readiness/blockers. Uses domain service math only. Read-only."
    )
    metadata = _DUAL_META
    input_model = CaseScopedInput
    output_model = OffboardingProgressAggregate

    def __init__(self, service: OffboardingService):
        self._service = service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CaseScopedInput)
        case, _ = _resolve_dual_mode_case(
            self._service,
            context,
            case_id=args.case_id,
            employee_id=args.employee_id,
        )

        checklist = _call_service(
            lambda: self._service.get_progress(case.id),
            error_message="Failed to load checklist progress",
        )
        clearance = _call_service(
            lambda: self._service.get_clearance_progress(case.id),
            error_message="Failed to load clearance progress",
        )
        interview = _call_service(
            lambda: self._service.get_exit_interview_for_hr(case.id),
            error_message="Failed to load exit interview",
        )
        readiness = _readiness_for_case(self._service, case)

        exit_brief = ExitInterviewStatusBrief(present=False)
        if interview is not None:
            exit_brief = ExitInterviewStatusBrief(
                present=True,
                status=_status_value(interview.status),
                scheduled_at=interview.scheduled_at,
                completed_at=interview.completed_at,
            )

        return OffboardingProgressAggregate(
            case_id=case.id,
            case_status=_status_value(case.status),
            checklist=ChecklistProgressBrief(
                total_tasks=checklist.total_tasks,
                completed_tasks=checklist.completed_tasks,
                pending_tasks=checklist.pending_tasks,
                in_progress_tasks=checklist.in_progress_tasks,
                skipped_tasks=checklist.skipped_tasks,
                required_total=checklist.required_total,
                required_completed=checklist.required_completed,
                percentage=checklist.percentage,
                required_complete=checklist.required_complete,
            ),
            clearance=ClearanceProgressBrief(
                total=clearance.total,
                pending=clearance.pending,
                cleared=clearance.cleared,
                not_applicable=clearance.not_applicable,
                percentage=clearance.percentage,
                clearance_complete=clearance.clearance_complete,
            ),
            exit_interview=exit_brief,
            ready_to_complete=readiness.ready,
            terminal=readiness.terminal,
            blockers=list(readiness.blockers),
        )


class ListOffboardingTasksTool(BaseTool):
    name = "list_offboarding_tasks"
    description = (
        "List offboarding checklist tasks for a case. "
        "HR: case_id or employee_id. Employees: own tasks. Optional status filter. "
        "Read-only."
    )
    metadata = _DUAL_META
    input_model = ListOffboardingTasksInput
    output_model = OffboardingTaskListResult

    def __init__(self, service: OffboardingService):
        self._service = service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListOffboardingTasksInput)
        use_hr = _should_use_hr_lookup(
            context, case_id=args.case_id, employee_id=args.employee_id
        )
        if use_hr:
            case = _resolve_hr_case(
                self._service, case_id=args.case_id, employee_id=args.employee_id
            )
            tasks = _call_service(
                lambda: self._service.list_tasks_for_hr(case.id),
                error_message="Failed to list offboarding tasks",
            )
            briefs = []
            for task in tasks:
                resp = build_task_response(task)
                briefs.append(
                    OffboardingTaskBrief(
                        task_id=resp.id,
                        title=resp.title,
                        category=_status_value(resp.category),
                        status=_status_value(resp.status),
                        is_required=resp.is_required,
                        assignee_name=(
                            resp.assigned_to.full_name if resp.assigned_to else None
                        ),
                        due_date=resp.due_date,
                        completed_at=resp.completed_at,
                    )
                )
        else:
            _require_employee_profile(context)
            if args.case_id is not None:
                _require_own_case_id(self._service, context, args.case_id)
            tasks = _call_service(
                lambda: self._service.list_tasks_for_user(context.user_id),
                error_message="Failed to list offboarding tasks",
            )
            if args.case_id is not None:
                tasks = [t for t in tasks if t.offboarding_case_id == args.case_id]
            briefs = []
            for task in tasks:
                resp = build_employee_task_response(task)
                briefs.append(
                    OffboardingTaskBrief(
                        task_id=resp.id,
                        title=resp.title,
                        category=_status_value(resp.category),
                        status=_status_value(resp.status),
                        is_required=resp.is_required,
                        assignee_name=None,
                        due_date=resp.due_date,
                        completed_at=resp.completed_at,
                    )
                )

        if args.status:
            wanted = args.status.strip().lower()
            briefs = [b for b in briefs if b.status.lower() == wanted]
        return OffboardingTaskListResult(tasks=briefs)


class GetOffboardingClearanceTool(BaseTool):
    name = "get_offboarding_clearance"
    description = (
        "Get clearance items (and HR progress counts) for an offboarding case. "
        "Read-only."
    )
    metadata = _DUAL_META
    input_model = CaseScopedInput
    output_model = OffboardingClearanceResult

    def __init__(self, service: OffboardingService):
        self._service = service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CaseScopedInput)
        case, use_hr_view = _resolve_dual_mode_case(
            self._service,
            context,
            case_id=args.case_id,
            employee_id=args.employee_id,
        )
        items = _call_service(
            lambda: self._service.list_clearance_for_hr(case.id),
            error_message="Failed to list clearance items",
        )
        progress = _call_service(
            lambda: self._service.get_clearance_progress(case.id),
            error_message="Failed to load clearance progress",
        )
        return OffboardingClearanceResult(
            case_id=case.id,
            items=[
                OffboardingClearanceItemBrief(
                    item_id=item.id,
                    category=_status_value(item.category),
                    item=item.item,
                    status=_status_value(item.status),
                    notes=(
                        item.notes
                        if use_hr_view
                        else build_employee_clearance_response(item).notes
                    ),
                    completed_at=item.completed_at,
                )
                for item in items
            ],
            progress=ClearanceProgressBrief(
                total=progress.total,
                pending=progress.pending,
                cleared=progress.cleared,
                not_applicable=progress.not_applicable,
                percentage=progress.percentage,
                clearance_complete=progress.clearance_complete,
            ),
        )


class GetExitInterviewTool(BaseTool):
    name = "get_exit_interview"
    description = (
        "Get the exit interview for an offboarding case (schedule, status, meeting URL). "
        "HR may see feedback; employees never see feedback. Read-only. No Meet APIs."
    )
    metadata = _DUAL_META
    input_model = CaseScopedInput
    output_model = ExitInterviewBrief

    def __init__(self, service: OffboardingService):
        self._service = service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CaseScopedInput)
        case, use_hr_view = _resolve_dual_mode_case(
            self._service,
            context,
            case_id=args.case_id,
            employee_id=args.employee_id,
        )
        interview = _call_service(
            lambda: self._service.get_exit_interview_for_hr(case.id),
            error_message="Failed to load exit interview",
        )
        if interview is None:
            raise ToolExecutionError("No exit interview for this case")
        if use_hr_view:
            resp = build_exit_interview_response(interview)
            return ExitInterviewBrief(
                exit_interview_id=resp.id,
                case_id=resp.offboarding_case_id,
                status=_status_value(resp.status),
                interviewer_name=(
                    resp.interviewer.full_name if resp.interviewer else None
                ),
                scheduled_at=resp.scheduled_at,
                ends_at=resp.ends_at,
                meeting_url=resp.meeting_url,
                meeting_available=bool(resp.meeting_url),
                feedback=resp.feedback,
                completed_at=resp.completed_at,
            )

        emp_view = build_employee_exit_interview_response(interview)
        return ExitInterviewBrief(
            exit_interview_id=emp_view.id,
            case_id=emp_view.offboarding_case_id,
            status=_status_value(emp_view.status),
            interviewer_name=(
                emp_view.interviewer.full_name if emp_view.interviewer else None
            ),
            scheduled_at=emp_view.scheduled_at,
            ends_at=emp_view.ends_at,
            meeting_url=emp_view.meeting_url,
            meeting_available=bool(emp_view.meeting_url),
            feedback=None,
            completed_at=None,
        )


class GetOffboardingReadinessTool(BaseTool):
    name = "get_offboarding_readiness"
    description = (
        "Whether an offboarding case can be completed and any blockers. "
        "Completed/cancelled cases return terminal=true without calling can_complete. "
        "Otherwise uses existing O.5 can_complete(). Read-only."
    )
    metadata = _DUAL_META
    input_model = CaseScopedInput
    output_model = OffboardingReadinessResult

    def __init__(self, service: OffboardingService):
        self._service = service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CaseScopedInput)
        case, _ = _resolve_dual_mode_case(
            self._service,
            context,
            case_id=args.case_id,
            employee_id=args.employee_id,
        )
        return _readiness_for_case(self._service, case)


class FindEmployeesForOffboardingTool(BaseTool):
    name = "find_employees_for_offboarding"
    description = (
        "HR only: search active employees by name for offboarding entity resolution. "
        "If count is 0 or greater than 1, ask the user to clarify; do not guess. "
        "Read-only."
    )
    metadata = _HR_META
    input_model = FindEmployeesForOffboardingInput
    output_model = FindEmployeesForOffboardingOutput

    def __init__(self, employee_service: EmployeeService):
        self._employees = employee_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, FindEmployeesForOffboardingInput)
        _require_hr(context)
        try:
            rows, _total = self._employees.list_employees(
                status="active", q=args.q.strip()
            )
        except AppException as exc:
            raise ToolExecutionError(exc.message) from exc
        except Exception as exc:
            raise ToolExecutionError("Failed to search employees") from exc

        matches = [
            OffboardingEmployeeMatch(
                employee_id=row.id,
                full_name=row.full_name,
                email=row.email,
                position=row.position,
                department=row.department.name if row.department else None,
                status=_status_value(row.employment_status),
            )
            for row in rows[: args.limit]
        ]
        message = None
        if len(matches) == 0:
            message = (
                "No active employees matched. Ask for a different name or employee_id."
            )
        elif len(matches) > 1:
            message = (
                "Multiple employees matched. Ask which employee_id to use; "
                "do not pick one automatically."
            )
        return FindEmployeesForOffboardingOutput(
            query=args.q.strip(),
            count=len(matches),
            employees=matches,
            message=message,
        )
