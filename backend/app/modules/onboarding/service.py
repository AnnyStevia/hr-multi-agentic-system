from datetime import UTC, datetime

from app.modules.documents.repository import DocumentRepository
from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.hr_access import list_hr_staff_user_ids
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.models import Onboarding, OnboardingStatus, OnboardingTask, OnboardingTaskStatus
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schemas import (
    DocumentCountResponse,
    OnboardingListItemResponse,
    OnboardingProgressResponse,
    OnboardingResponse,
    OnboardingTaskCreateRequest,
    OnboardingTaskResponse,
    OnboardingTaskUpdateRequest,
    ProgressCountResponse,
)
from app.modules.training.models import OnboardingTrainingStatus
from app.modules.training.repository import TrainingRepository
from app.shared.exceptions import AppException


class OnboardingService:
    def __init__(
        self,
        repository: OnboardingRepository,
        employees: EmployeeRepository,
        notifications: NotificationService | None = None,
        documents: DocumentRepository | None = None,
        trainings: TrainingRepository | None = None,
    ):
        self.repository = repository
        self.employees = employees
        self.notifications = notifications
        self.documents = documents
        self.trainings = trainings

    def create_for_employee(self, employee_id: int, *, commit: bool = True) -> Onboarding:
        if self.repository.get_by_employee_id(employee_id) is not None:
            raise AppException(
                "An onboarding record already exists for this employee",
                status_code=409,
            )
        return self.repository.add(self._new_onboarding(employee_id), commit=commit)

    def backfill_missing_onboardings(self, *, commit: bool = True) -> int:
        employee_ids = self.repository.list_employee_ids_without_onboarding()
        created = 0
        for employee_id in employee_ids:
            self.repository.add(self._new_onboarding(employee_id), commit=False)
            created += 1
        if commit and created:
            self.repository.db.commit()
        return created

    @staticmethod
    def _new_onboarding(employee_id: int) -> Onboarding:
        return Onboarding(
            employee_id=employee_id,
            status=OnboardingStatus.IN_PROGRESS,
            started_at=datetime.now(UTC),
        )

    def get_for_hr(self, onboarding_id: int) -> Onboarding:
        onboarding = self.repository.get_by_id(onboarding_id)
        if onboarding is None:
            raise AppException("Onboarding not found", status_code=404)
        return onboarding

    def get_by_employee_id_for_hr(self, employee_id: int) -> Onboarding:
        if self.employees.get_by_id(employee_id) is None:
            raise AppException("Employee not found", status_code=404)
        onboarding = self.repository.get_by_employee_id(employee_id)
        if onboarding is None:
            raise AppException("Onboarding not found", status_code=404)
        return onboarding

    def list_for_hr(self) -> list[OnboardingListItemResponse]:
        rows = self.repository.list_for_hr()
        return [build_onboarding_list_item(onboarding) for onboarding in rows]

    def get_for_employee_user(self, user_id: int) -> Onboarding:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Onboarding not found", status_code=404)
        onboarding = self.repository.get_by_employee_id(employee.id)
        if onboarding is None:
            raise AppException("Onboarding not found", status_code=404)
        return onboarding

    def get_active_onboarding_for_user(self, user_id: int) -> Onboarding | None:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            return None
        onboarding = self.repository.get_by_employee_id(employee.id)
        if onboarding is None or onboarding.status != OnboardingStatus.IN_PROGRESS:
            return None
        return onboarding

    def get_onboarding_status_for_user(self, user_id: int) -> OnboardingStatus | None:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            return None
        onboarding = self.repository.get_by_employee_id(employee.id)
        return onboarding.status if onboarding else None

    def complete_for_hr(self, onboarding_id: int) -> Onboarding:
        onboarding = self.get_for_hr(onboarding_id)
        if onboarding.status == OnboardingStatus.COMPLETED:
            raise AppException("Onboarding is already completed", status_code=400)
        onboarding.status = OnboardingStatus.COMPLETED
        onboarding.completed_at = datetime.now(UTC)
        return self.repository.save(onboarding)

    def list_tasks_for_hr(self, onboarding_id: int) -> list[OnboardingTask]:
        self.get_for_hr(onboarding_id)
        return self.repository.list_tasks_by_onboarding_id(onboarding_id)

    def create_task(
        self, onboarding_id: int, payload: OnboardingTaskCreateRequest
    ) -> OnboardingTask:
        onboarding = self.get_for_hr(onboarding_id)
        if onboarding.status == OnboardingStatus.COMPLETED:
            raise AppException(
                "Cannot add tasks to a completed onboarding",
                status_code=400,
            )
        description = payload.description.strip() if payload.description else None
        if description == "":
            description = None
        task = OnboardingTask(
            onboarding_id=onboarding_id,
            title=payload.title.strip(),
            description=description,
            status=OnboardingTaskStatus.PENDING,
            due_date=payload.due_date,
        )
        saved = self.repository.add_task(task)
        self._notify_task_assigned(onboarding, saved)
        return saved

    def update_task(self, task_id: int, payload: OnboardingTaskUpdateRequest) -> OnboardingTask:
        task = self.repository.get_task_by_id(task_id)
        if task is None:
            raise AppException("Onboarding task not found", status_code=404)

        data = payload.model_dump(exclude_unset=True)
        status_became_completed = False
        if "title" in data and data["title"] is not None:
            task.title = data["title"].strip()
        if "description" in data:
            description = data["description"]
            if description is not None:
                description = description.strip() or None
            task.description = description
        if "due_date" in data:
            task.due_date = data["due_date"]
        if "status" in data and data["status"] is not None:
            new_status = data["status"]
            if new_status == OnboardingTaskStatus.COMPLETED:
                if task.status != OnboardingTaskStatus.COMPLETED:
                    status_became_completed = True
                task.status = OnboardingTaskStatus.COMPLETED
                if task.completed_at is None:
                    task.completed_at = datetime.now(UTC)
            elif new_status == OnboardingTaskStatus.PENDING:
                task.status = OnboardingTaskStatus.PENDING
                task.completed_at = None

        saved = self.repository.save_task(task)
        if status_became_completed:
            self._maybe_complete_onboarding(saved.onboarding_id)
        return saved

    def delete_task(self, task_id: int) -> None:
        task = self.repository.get_task_by_id(task_id)
        if task is None:
            raise AppException("Onboarding task not found", status_code=404)
        onboarding_id = task.onboarding_id
        self.repository.delete_task(task)
        self._maybe_complete_onboarding(onboarding_id)

    def list_tasks_for_employee_user(self, user_id: int) -> list[OnboardingTask]:
        onboarding = self.get_for_employee_user(user_id)
        return self.repository.list_tasks_by_onboarding_id(onboarding.id)

    def complete_task_for_employee_user(self, user_id: int, task_id: int) -> OnboardingTask:
        task = self.repository.get_task_by_id(task_id)
        if task is None:
            raise AppException("Onboarding task not found", status_code=404)

        employee = self.employees.get_by_id(task.onboarding.employee_id)
        if employee is None or employee.user_id != user_id:
            raise AppException("Onboarding task not found", status_code=404)

        if task.status == OnboardingTaskStatus.COMPLETED:
            raise AppException("Task is already completed", status_code=400)

        task.status = OnboardingTaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        saved = self.repository.save_task(task)
        self._notify_task_completed(saved)
        self._maybe_complete_onboarding(saved.onboarding_id)
        return saved

    def notify_onboarding_started(self, employee: Employee) -> None:
        if self.notifications is None or employee.user_id is None:
            return
        onboarding = self.repository.get_by_employee_id(employee.id)
        if onboarding is None:
            return
        self.notifications.create_if_absent(
            recipient_user_id=employee.user_id,
            type=NotificationType.ONBOARDING_STARTED,
            title="Onboarding started",
            message=(
                "Welcome! Your onboarding has started. "
                "Open your onboarding checklist to get started."
            ),
            related_entity_type="onboarding",
            related_entity_id=onboarding.id,
        )

    def _notify_task_assigned(self, onboarding: Onboarding, task: OnboardingTask) -> None:
        if self.notifications is None:
            return
        employee = self.employees.get_by_id(onboarding.employee_id)
        if employee is None or employee.user_id is None:
            return
        self.notifications.create_notification(
            recipient_user_id=employee.user_id,
            type=NotificationType.ONBOARDING_TASK_ASSIGNED,
            title="New onboarding task",
            message=f'You have a new onboarding task: "{task.title}".',
            related_entity_type="onboarding",
            related_entity_id=onboarding.id,
        )

    def _notify_task_completed(self, task: OnboardingTask) -> None:
        if self.notifications is None:
            return
        employee = self.employees.get_by_id(task.onboarding.employee_id)
        if employee is None:
            return
        employee_name = employee.full_name
        for recipient_id in list_hr_staff_user_ids(self.repository.db):
            if employee.user_id is not None and recipient_id == employee.user_id:
                continue
            self.notifications.create_if_absent(
                recipient_user_id=recipient_id,
                type=NotificationType.ONBOARDING_TASK_COMPLETED,
                title="Onboarding task completed",
                message=f'{employee_name} completed the onboarding task "{task.title}".',
                related_entity_type="onboarding_task",
                related_entity_id=task.id,
            )

    def _notify_onboarding_completed(self, onboarding: Onboarding, employee: Employee) -> None:
        if self.notifications is None:
            return
        employee_name = employee.full_name
        if employee.user_id is not None:
            self.notifications.create_if_absent(
                recipient_user_id=employee.user_id,
                type=NotificationType.ONBOARDING_COMPLETED,
                title="Onboarding complete",
                message="Congratulations — your onboarding is complete. You now have full employee access.",
                related_entity_type="onboarding",
                related_entity_id=onboarding.id,
            )
        for recipient_id in list_hr_staff_user_ids(self.repository.db):
            if employee.user_id is not None and recipient_id == employee.user_id:
                continue
            self.notifications.create_if_absent(
                recipient_user_id=recipient_id,
                type=NotificationType.ONBOARDING_COMPLETED,
                title="Onboarding complete",
                message=f"{employee_name} has completed onboarding.",
                related_entity_type="onboarding",
                related_entity_id=onboarding.id,
            )

    def _maybe_complete_onboarding(self, onboarding_id: int) -> None:
        onboarding = self.repository.get_by_id(onboarding_id)
        if onboarding is None or onboarding.status == OnboardingStatus.COMPLETED:
            return
        tasks = self.repository.list_tasks_by_onboarding_id(onboarding_id)
        if not tasks:
            return
        if any(task.status != OnboardingTaskStatus.COMPLETED for task in tasks):
            return
        onboarding.status = OnboardingStatus.COMPLETED
        onboarding.completed_at = datetime.now(UTC)
        saved = self.repository.save(onboarding)
        employee = self.employees.get_by_id(saved.employee_id)
        if employee is not None:
            self._notify_onboarding_completed(saved, employee)

    def get_progress_for_hr(self, onboarding_id: int) -> OnboardingProgressResponse:
        onboarding = self.get_for_hr(onboarding_id)
        return self._build_progress(onboarding)

    def get_progress_for_employee_user(self, user_id: int) -> OnboardingProgressResponse:
        onboarding = self.get_for_employee_user(user_id)
        return self._build_progress(onboarding)

    def _build_progress(self, onboarding: Onboarding) -> OnboardingProgressResponse:
        tasks = self.repository.list_tasks_by_onboarding_id(onboarding.id)
        task_total = len(tasks)
        task_completed = sum(1 for task in tasks if task.status == OnboardingTaskStatus.COMPLETED)
        task_pending = task_total - task_completed

        if self.trainings is not None:
            assignments = self.trainings.list_assignments(onboarding.id)
        else:
            assignments = []
        training_total = len(assignments)
        training_completed = sum(
            1 for item in assignments if item.status == OnboardingTrainingStatus.COMPLETED
        )
        training_pending = training_total - training_completed

        if self.documents is not None:
            document_total = len(self.documents.list_by_employee_id(onboarding.employee_id))
        else:
            document_total = 0

        denominator = task_total + training_total
        if denominator == 0:
            overall_percentage = 0
        else:
            overall_percentage = round(
                (task_completed + training_completed) / denominator * 100
            )

        return OnboardingProgressResponse(
            onboarding_id=onboarding.id,
            status=onboarding.status,
            completed_at=onboarding.completed_at,
            tasks=ProgressCountResponse(
                total=task_total,
                completed=task_completed,
                pending=task_pending,
            ),
            trainings=ProgressCountResponse(
                total=training_total,
                completed=training_completed,
                pending=training_pending,
            ),
            documents=DocumentCountResponse(total=document_total),
            overall_percentage=overall_percentage,
        )


def build_onboarding_list_item(onboarding: Onboarding) -> OnboardingListItemResponse:
    total = len(onboarding.tasks)
    completed = sum(1 for task in onboarding.tasks if task.status == OnboardingTaskStatus.COMPLETED)
    return OnboardingListItemResponse(
        id=onboarding.id,
        employee_id=onboarding.employee_id,
        employee_name=onboarding.employee.full_name,
        position=onboarding.employee.position,
        status=onboarding.status,
        started_at=onboarding.started_at,
        completed_at=onboarding.completed_at,
        completed_tasks_count=completed,
        total_tasks_count=total,
    )


def build_onboarding_response(onboarding: Onboarding) -> OnboardingResponse:
    return OnboardingResponse.model_validate(onboarding)


def build_onboarding_task_response(task: OnboardingTask) -> OnboardingTaskResponse:
    return OnboardingTaskResponse.model_validate(task)
