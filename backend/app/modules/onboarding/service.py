from datetime import UTC, datetime

from app.modules.employees.repository import EmployeeRepository
from app.modules.onboarding.models import Onboarding, OnboardingStatus, OnboardingTask, OnboardingTaskStatus
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schemas import (
    OnboardingListItemResponse,
    OnboardingResponse,
    OnboardingTaskCreateRequest,
    OnboardingTaskResponse,
    OnboardingTaskUpdateRequest,
)
from app.shared.exceptions import AppException


class OnboardingService:
    def __init__(self, repository: OnboardingRepository, employees: EmployeeRepository):
        self.repository = repository
        self.employees = employees

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
        self.get_for_hr(onboarding_id)
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
        return self.repository.add_task(task)

    def update_task(self, task_id: int, payload: OnboardingTaskUpdateRequest) -> OnboardingTask:
        task = self.repository.get_task_by_id(task_id)
        if task is None:
            raise AppException("Onboarding task not found", status_code=404)

        data = payload.model_dump(exclude_unset=True)
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
                task.status = OnboardingTaskStatus.COMPLETED
                if task.completed_at is None:
                    task.completed_at = datetime.now(UTC)
            elif new_status == OnboardingTaskStatus.PENDING:
                task.status = OnboardingTaskStatus.PENDING
                task.completed_at = None

        return self.repository.save_task(task)

    def delete_task(self, task_id: int) -> None:
        task = self.repository.get_task_by_id(task_id)
        if task is None:
            raise AppException("Onboarding task not found", status_code=404)
        self.repository.delete_task(task)

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
        return self.repository.save_task(task)


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
