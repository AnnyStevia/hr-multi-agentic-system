from datetime import UTC, date, datetime

from app.modules.employees.models import EmploymentStatus
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.models import User
from app.modules.offboarding.models import (
    ACTIVE_OFFBOARDING_STATUSES,
    TERMINAL_TASK_STATUSES,
    OffboardingCase,
    OffboardingStatus,
    OffboardingTask,
    OffboardingTaskStatus,
)
from app.modules.offboarding.repository import OffboardingRepository
from app.modules.offboarding.schemas import (
    OffboardingCreateRequest,
    OffboardingCreatedBySummary,
    OffboardingDetailResponse,
    OffboardingEmployeeSummary,
    OffboardingEmployeeViewResponse,
    OffboardingListItemResponse,
    OffboardingProgressResponse,
    OffboardingTaskAssigneeSummary,
    OffboardingTaskCreateRequest,
    OffboardingTaskEmployeeViewResponse,
    OffboardingTaskResponse,
    OffboardingTaskUpdateRequest,
)
from app.modules.offboarding.templates import DEFAULT_OFFBOARDING_TASK_TEMPLATES
from app.shared.exceptions import AppException


class OffboardingService:
    def __init__(
        self,
        repository: OffboardingRepository,
        employees: EmployeeRepository,
    ):
        self.repository = repository
        self.employees = employees

    def create_for_hr(self, actor: User, payload: OffboardingCreateRequest) -> OffboardingCase:
        employee = self.employees.get_by_id(payload.employee_id)
        if employee is None:
            raise AppException("Employee not found", status_code=404)
        if employee.employment_status != EmploymentStatus.ACTIVE:
            raise AppException("Employee must be active to start offboarding", status_code=400)

        initiated_at = datetime.now(UTC)
        if payload.last_working_day < initiated_at.date():
            raise AppException(
                "Last working day cannot be before the initiation date",
                status_code=400,
            )

        if self.repository.get_active_for_employee(payload.employee_id) is not None:
            raise AppException(
                "An active offboarding case already exists for this employee",
                status_code=409,
            )

        reason_details = payload.reason_details.strip() if payload.reason_details else None
        if reason_details == "":
            reason_details = None

        case = OffboardingCase(
            employee_id=payload.employee_id,
            reason=payload.reason,
            reason_details=reason_details,
            last_working_day=payload.last_working_day,
            status=OffboardingStatus.INITIATED,
            initiated_at=initiated_at,
            created_by_user_id=actor.id,
        )
        try:
            self.repository.add(case, commit=False)
            self._seed_default_tasks(case)
            self.repository.commit()
            self.repository.db.refresh(case)
        except Exception:
            self.repository.rollback()
            raise
        return case

    def _seed_default_tasks(self, case: OffboardingCase) -> None:
        for template in DEFAULT_OFFBOARDING_TASK_TEMPLATES:
            self.repository.add_task(
                OffboardingTask(
                    offboarding_case_id=case.id,
                    title=template.title,
                    description=template.description,
                    category=template.category,
                    status=OffboardingTaskStatus.PENDING,
                    is_required=template.is_required,
                ),
                commit=False,
            )

    def list_for_hr(
        self,
        *,
        status: OffboardingStatus | None = None,
        employee_id: int | None = None,
    ) -> list[OffboardingListItemResponse]:
        return [
            build_list_item_response(case)
            for case in self.repository.list_for_hr(
                status=status,
                employee_id=employee_id,
            )
        ]

    def get_for_hr(self, case_id: int) -> OffboardingCase:
        case = self.repository.get_by_id(case_id)
        if case is None:
            raise AppException("Offboarding case not found", status_code=404)
        return case

    def list_for_user(self, user_id: int) -> list[OffboardingCase]:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee record not found for this user", status_code=404)
        return self.repository.list_for_employee(employee.id)

    def _require_mutable_case(self, case: OffboardingCase) -> None:
        if case.status not in ACTIVE_OFFBOARDING_STATUSES:
            raise AppException(
                f"Cannot modify tasks for offboarding case with status '{case.status.value}'",
                status_code=400,
            )

    def _resolve_assignee(self, employee_id: int | None) -> None:
        if employee_id is None:
            return
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise AppException("Assigned employee not found", status_code=404)
        if employee.employment_status != EmploymentStatus.ACTIVE:
            raise AppException("Assigned employee must be active", status_code=400)

    def _validate_due_date(self, case: OffboardingCase, due: date | None) -> None:
        if due is None:
            return
        if due < case.initiated_at.date():
            raise AppException(
                "Due date cannot be before the offboarding initiation date",
                status_code=400,
            )

    def list_tasks_for_hr(self, case_id: int) -> list[OffboardingTask]:
        self.get_for_hr(case_id)
        return self.repository.list_tasks_for_case(case_id)

    def get_progress(self, case_id: int) -> OffboardingProgressResponse:
        self.get_for_hr(case_id)
        tasks = self.repository.list_tasks_for_case(case_id)
        return build_progress_response(case_id, tasks)

    def create_task_for_hr(
        self, case_id: int, payload: OffboardingTaskCreateRequest
    ) -> OffboardingTask:
        case = self.get_for_hr(case_id)
        self._require_mutable_case(case)
        title = payload.title.strip()
        if not title:
            raise AppException("Title is required", status_code=400)
        self._resolve_assignee(payload.assigned_to_employee_id)
        self._validate_due_date(case, payload.due_date)
        description = payload.description.strip() if payload.description else None
        if description == "":
            description = None
        task = OffboardingTask(
            offboarding_case_id=case.id,
            title=title,
            description=description,
            category=payload.category,
            status=OffboardingTaskStatus.PENDING,
            is_required=payload.is_required,
            assigned_to_employee_id=payload.assigned_to_employee_id,
            due_date=payload.due_date,
        )
        return self.repository.add_task(task)

    def update_task_for_hr(
        self, case_id: int, task_id: int, payload: OffboardingTaskUpdateRequest
    ) -> OffboardingTask:
        case = self.get_for_hr(case_id)
        self._require_mutable_case(case)
        task = self.repository.get_task_for_case(case_id, task_id)
        if task is None:
            raise AppException("Offboarding task not found", status_code=404)
        if task.status in TERMINAL_TASK_STATUSES:
            raise AppException("Completed or skipped tasks cannot be edited", status_code=400)

        if payload.title is not None:
            title = payload.title.strip()
            if not title:
                raise AppException("Title is required", status_code=400)
            task.title = title
        if payload.description is not None:
            description = payload.description.strip()
            task.description = description or None
        if payload.category is not None:
            task.category = payload.category
        if payload.is_required is not None:
            task.is_required = payload.is_required
        if payload.clear_assignee:
            task.assigned_to_employee_id = None
        elif payload.assigned_to_employee_id is not None:
            self._resolve_assignee(payload.assigned_to_employee_id)
            task.assigned_to_employee_id = payload.assigned_to_employee_id
        if payload.clear_due_date:
            task.due_date = None
        elif payload.due_date is not None:
            self._validate_due_date(case, payload.due_date)
            task.due_date = payload.due_date
        return self.repository.save_task(task)

    def start_task_for_hr(self, case_id: int, task_id: int) -> OffboardingTask:
        case = self.get_for_hr(case_id)
        self._require_mutable_case(case)
        task = self.repository.get_task_for_case(case_id, task_id)
        if task is None:
            raise AppException("Offboarding task not found", status_code=404)
        return self._start_task(task)

    def complete_task_for_hr(
        self, case_id: int, task_id: int, actor: User
    ) -> OffboardingTask:
        case = self.get_for_hr(case_id)
        self._require_mutable_case(case)
        task = self.repository.get_task_for_case(case_id, task_id)
        if task is None:
            raise AppException("Offboarding task not found", status_code=404)
        return self._complete_task(task, actor)

    def skip_task_for_hr(self, case_id: int, task_id: int) -> OffboardingTask:
        case = self.get_for_hr(case_id)
        self._require_mutable_case(case)
        task = self.repository.get_task_for_case(case_id, task_id)
        if task is None:
            raise AppException("Offboarding task not found", status_code=404)
        if task.status in TERMINAL_TASK_STATUSES:
            raise AppException(
                f"Cannot skip task from status '{task.status.value}'",
                status_code=400,
            )
        if task.status not in {
            OffboardingTaskStatus.PENDING,
            OffboardingTaskStatus.IN_PROGRESS,
        }:
            raise AppException(
                f"Cannot skip task from status '{task.status.value}'",
                status_code=400,
            )
        task.status = OffboardingTaskStatus.SKIPPED
        return self.repository.save_task(task)

    def reopen_task_for_hr(self, case_id: int, task_id: int) -> OffboardingTask:
        case = self.get_for_hr(case_id)
        self._require_mutable_case(case)
        task = self.repository.get_task_for_case(case_id, task_id)
        if task is None:
            raise AppException("Offboarding task not found", status_code=404)
        if task.status != OffboardingTaskStatus.IN_PROGRESS:
            raise AppException(
                f"Cannot reopen task from status '{task.status.value}'",
                status_code=400,
            )
        task.status = OffboardingTaskStatus.PENDING
        return self.repository.save_task(task)

    def list_tasks_for_user(self, user_id: int) -> list[OffboardingTask]:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee record not found for this user", status_code=404)
        return self.repository.list_tasks_assigned_to_employee(employee.id)

    def start_task_for_user(self, user_id: int, task_id: int) -> OffboardingTask:
        task = self._get_assigned_task_for_user(user_id, task_id)
        self._require_mutable_case(task.offboarding_case)
        return self._start_task(task)

    def complete_task_for_user(self, user_id: int, task_id: int, actor: User) -> OffboardingTask:
        task = self._get_assigned_task_for_user(user_id, task_id)
        self._require_mutable_case(task.offboarding_case)
        return self._complete_task(task, actor)

    def _get_assigned_task_for_user(self, user_id: int, task_id: int) -> OffboardingTask:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee record not found for this user", status_code=404)
        task = self.repository.get_task_by_id(task_id)
        if task is None or task.assigned_to_employee_id != employee.id:
            raise AppException("Offboarding task not found", status_code=404)
        return task

    def _start_task(self, task: OffboardingTask) -> OffboardingTask:
        if task.status != OffboardingTaskStatus.PENDING:
            raise AppException(
                f"Cannot start task from status '{task.status.value}'",
                status_code=400,
            )
        task.status = OffboardingTaskStatus.IN_PROGRESS
        return self.repository.save_task(task)

    def _complete_task(self, task: OffboardingTask, actor: User) -> OffboardingTask:
        if task.status not in {
            OffboardingTaskStatus.PENDING,
            OffboardingTaskStatus.IN_PROGRESS,
        }:
            raise AppException(
                f"Cannot complete task from status '{task.status.value}'",
                status_code=400,
            )
        task.status = OffboardingTaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        task.completed_by_user_id = actor.id
        return self.repository.save_task(task)

    def start(self, case_id: int) -> OffboardingCase:
        case = self.get_for_hr(case_id)
        allowed = {OffboardingStatus.INITIATED, OffboardingStatus.PENDING_CLEARANCE}
        if case.status not in allowed:
            raise AppException(
                f"Cannot start offboarding from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.IN_PROGRESS
        return self.repository.save(case)

    def move_to_pending_clearance(self, case_id: int) -> OffboardingCase:
        case = self.get_for_hr(case_id)
        if case.status != OffboardingStatus.IN_PROGRESS:
            raise AppException(
                f"Cannot move to pending clearance from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.PENDING_CLEARANCE
        return self.repository.save(case)

    def complete(self, case_id: int) -> OffboardingCase:
        """Complete when PENDING_CLEARANCE.

        Phase O.2: checklist progress is tracked but does not gate completion yet.
        """
        case = self.get_for_hr(case_id)
        if case.status != OffboardingStatus.PENDING_CLEARANCE:
            raise AppException(
                f"Cannot complete offboarding from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.COMPLETED
        case.completed_at = datetime.now(UTC)
        return self.repository.save(case)

    def cancel(self, case_id: int) -> OffboardingCase:
        case = self.get_for_hr(case_id)
        allowed = {
            OffboardingStatus.INITIATED,
            OffboardingStatus.IN_PROGRESS,
            OffboardingStatus.PENDING_CLEARANCE,
        }
        if case.status not in allowed:
            raise AppException(
                f"Cannot cancel offboarding from status '{case.status.value}'",
                status_code=400,
            )
        case.status = OffboardingStatus.CANCELLED
        return self.repository.save(case)


def _is_overdue(task: OffboardingTask, *, today: date | None = None) -> bool:
    if task.due_date is None:
        return False
    if task.status in TERMINAL_TASK_STATUSES:
        return False
    check_day = today or date.today()
    return task.due_date < check_day


def build_progress_response(
    case_id: int, tasks: list[OffboardingTask]
) -> OffboardingProgressResponse:
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == OffboardingTaskStatus.COMPLETED)
    skipped = sum(1 for t in tasks if t.status == OffboardingTaskStatus.SKIPPED)
    pending = sum(1 for t in tasks if t.status == OffboardingTaskStatus.PENDING)
    in_progress = sum(1 for t in tasks if t.status == OffboardingTaskStatus.IN_PROGRESS)
    required = [t for t in tasks if t.is_required]
    required_total = len(required)
    required_completed = sum(
        1 for t in required if t.status == OffboardingTaskStatus.COMPLETED
    )
    percentage = round(completed / total * 100) if total else 0
    overdue = sum(1 for t in tasks if _is_overdue(t))
    return OffboardingProgressResponse(
        offboarding_case_id=case_id,
        total_tasks=total,
        completed_tasks=completed,
        skipped_tasks=skipped,
        pending_tasks=pending,
        in_progress_tasks=in_progress,
        required_total=required_total,
        required_completed=required_completed,
        percentage=percentage,
        required_complete=required_completed == required_total,
        overdue_tasks=overdue,
    )


def build_task_response(task: OffboardingTask) -> OffboardingTaskResponse:
    assigned_to = None
    if task.assigned_to is not None:
        assigned_to = OffboardingTaskAssigneeSummary(
            id=task.assigned_to.id,
            full_name=task.assigned_to.full_name,
            email=task.assigned_to.email,
        )
    return OffboardingTaskResponse(
        id=task.id,
        offboarding_case_id=task.offboarding_case_id,
        title=task.title,
        description=task.description,
        category=task.category,
        status=task.status,
        is_required=task.is_required,
        assigned_to_employee_id=task.assigned_to_employee_id,
        assigned_to=assigned_to,
        due_date=task.due_date,
        is_overdue=_is_overdue(task),
        completed_at=task.completed_at,
        completed_by_user_id=task.completed_by_user_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def build_employee_task_response(task: OffboardingTask) -> OffboardingTaskEmployeeViewResponse:
    return OffboardingTaskEmployeeViewResponse(
        id=task.id,
        offboarding_case_id=task.offboarding_case_id,
        title=task.title,
        description=task.description,
        category=task.category,
        status=task.status,
        is_required=task.is_required,
        due_date=task.due_date,
        is_overdue=_is_overdue(task),
        completed_at=task.completed_at,
    )


def build_list_item_response(case: OffboardingCase) -> OffboardingListItemResponse:
    employee = case.employee
    return OffboardingListItemResponse(
        id=case.id,
        employee_id=case.employee_id,
        employee_name=employee.full_name,
        employee_email=employee.email,
        position=employee.position,
        reason=case.reason,
        last_working_day=case.last_working_day,
        status=case.status,
        initiated_at=case.initiated_at,
    )


def build_detail_response(case: OffboardingCase) -> OffboardingDetailResponse:
    employee = case.employee
    created_by = None
    if case.created_by is not None:
        created_by = OffboardingCreatedBySummary(
            id=case.created_by.id,
            full_name=f"{case.created_by.first_name} {case.created_by.last_name}".strip(),
            email=case.created_by.email,
        )
    return OffboardingDetailResponse(
        id=case.id,
        employee_id=case.employee_id,
        employee=OffboardingEmployeeSummary(
            id=employee.id,
            full_name=employee.full_name,
            email=employee.email,
            position=employee.position,
            employee_number=employee.employee_number,
        ),
        reason=case.reason,
        reason_details=case.reason_details,
        last_working_day=case.last_working_day,
        status=case.status,
        initiated_at=case.initiated_at,
        completed_at=case.completed_at,
        created_by=created_by,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def build_employee_view_response(case: OffboardingCase) -> OffboardingEmployeeViewResponse:
    return OffboardingEmployeeViewResponse(
        id=case.id,
        status=case.status,
        reason=case.reason,
        last_working_day=case.last_working_day,
        initiated_at=case.initiated_at,
        completed_at=case.completed_at,
    )
