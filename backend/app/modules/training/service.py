from datetime import UTC, datetime

from app.modules.employees.repository import EmployeeRepository
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.models import OnboardingTaskType
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.sync import sync_onboarding_tasks_for_employee
from app.modules.training.models import (
    EmployeeTrainingProgress,
    OnboardingTraining,
    OnboardingTrainingStatus,
    Training,
)
from app.modules.training.repository import TrainingRepository
from app.modules.training.schemas import (
    MyTrainingResourceResponse,
    OnboardingTrainingAssignRequest,
    OnboardingTrainingResponse,
    TrainingCreateRequest,
    TrainingResponse,
    TrainingUpdateRequest,
)
from app.shared.exceptions import AppException


class TrainingService:
    def __init__(
        self,
        repository: TrainingRepository,
        onboardings: OnboardingRepository,
        employees: EmployeeRepository,
        notifications: NotificationService | None = None,
    ):
        self.repository = repository
        self.onboardings = onboardings
        self.employees = employees
        self.notifications = notifications

    def list_trainings(self) -> list[Training]:
        return self.repository.list_trainings()

    def create_training(self, payload: TrainingCreateRequest) -> Training:
        description = payload.description.strip() if payload.description else None
        if description == "":
            description = None
        training = Training(
            title=payload.title.strip(),
            description=description,
            resource_url=payload.resource_url,
        )
        saved = self.repository.add_training(training)
        self._notify_training_resource_published(saved)
        return saved

    def update_training(self, training_id: int, payload: TrainingUpdateRequest) -> Training:
        training = self.repository.get_training(training_id)
        if training is None:
            raise AppException("Training not found", status_code=404)
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            training.title = data["title"].strip()
        if "description" in data:
            description = data["description"]
            if description is not None:
                description = description.strip() or None
            training.description = description
        if "resource_url" in data:
            training.resource_url = data["resource_url"]
        return self.repository.save_training(training)

    def delete_training(self, training_id: int) -> None:
        training = self.repository.get_training(training_id)
        if training is None:
            raise AppException("Training not found", status_code=404)
        self.repository.delete_training(training)

    def list_assignments_for_hr(self, onboarding_id: int) -> list[OnboardingTraining]:
        if self.onboardings.get_by_id(onboarding_id) is None:
            raise AppException("Onboarding not found", status_code=404)
        return self.repository.list_assignments(onboarding_id)

    def assign_training(
        self, onboarding_id: int, payload: OnboardingTrainingAssignRequest
    ) -> OnboardingTraining:
        if self.onboardings.get_by_id(onboarding_id) is None:
            raise AppException("Onboarding not found", status_code=404)
        training = self.repository.get_training(payload.training_id)
        if training is None:
            raise AppException("Training not found", status_code=404)
        if self.repository.find_assignment(onboarding_id, payload.training_id) is not None:
            raise AppException("Training is already assigned to this onboarding", status_code=409)
        assignment = OnboardingTraining(
            onboarding_id=onboarding_id,
            training_id=payload.training_id,
            status=OnboardingTrainingStatus.PENDING,
            assigned_at=datetime.now(UTC),
        )
        saved = self.repository.add_assignment(assignment)
        self._notify_training_assigned(saved, training)
        onboarding = self.onboardings.get_by_id(onboarding_id)
        if onboarding is not None:
            sync_onboarding_tasks_for_employee(
                self.repository.db,
                onboarding.employee_id,
                task_types={OnboardingTaskType.TRAINING},
            )
        return saved

    def remove_assignment(self, onboarding_id: int, assignment_id: int) -> None:
        onboarding = self.onboardings.get_by_id(onboarding_id)
        if onboarding is None:
            raise AppException("Onboarding not found", status_code=404)
        assignment = self.repository.get_assignment_for_onboarding(assignment_id, onboarding_id)
        if assignment is None:
            raise AppException("Training assignment not found", status_code=404)
        employee_id = onboarding.employee_id
        self.repository.delete_assignment(assignment)
        sync_onboarding_tasks_for_employee(
            self.repository.db,
            employee_id,
            task_types={OnboardingTaskType.TRAINING},
        )

    def list_assignments_for_user(self, user_id: int) -> list[OnboardingTraining]:
        onboarding = self._onboarding_for_user(user_id)
        if onboarding is None:
            return []
        return self.repository.list_assignments(onboarding.id)

    def list_catalogue_for_user(self, user_id: int) -> list[MyTrainingResourceResponse]:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)

        progress_by_id = {
            row.training_id: row
            for row in self.repository.list_progress_for_employee(employee.id)
        }
        assignment_by_id: dict[int, OnboardingTraining] = {}
        onboarding = self.onboardings.get_by_employee_id(employee.id)
        if onboarding is not None:
            for assignment in self.repository.list_assignments(onboarding.id):
                assignment_by_id[assignment.training_id] = assignment

        items: list[MyTrainingResourceResponse] = []
        for training in self.repository.list_trainings_newest_first():
            progress = progress_by_id.get(training.id)
            assignment = assignment_by_id.get(training.id)
            completed = False
            completed_at = None
            if progress is not None and progress.status == OnboardingTrainingStatus.COMPLETED:
                completed = True
                completed_at = progress.completed_at
            elif (
                assignment is not None
                and assignment.status == OnboardingTrainingStatus.COMPLETED
            ):
                completed = True
                completed_at = assignment.completed_at

            items.append(
                MyTrainingResourceResponse(
                    training_id=training.id,
                    title=training.title,
                    description=training.description,
                    resource_url=training.resource_url,
                    status=(
                        OnboardingTrainingStatus.COMPLETED
                        if completed
                        else OnboardingTrainingStatus.PENDING
                    ),
                    completed_at=completed_at,
                    created_at=training.created_at,
                    updated_at=training.updated_at,
                )
            )
        return items

    def complete_training_for_user(
        self, user_id: int, training_id: int
    ) -> MyTrainingResourceResponse:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        training = self.repository.get_training(training_id)
        if training is None:
            raise AppException("Training not found", status_code=404)

        now = datetime.now(UTC)
        progress = self.repository.get_progress(employee.id, training_id)
        if progress is None:
            progress = EmployeeTrainingProgress(
                employee_id=employee.id,
                training_id=training_id,
                status=OnboardingTrainingStatus.COMPLETED,
                completed_at=now,
            )
            progress = self.repository.add_progress(progress)
        elif progress.status != OnboardingTrainingStatus.COMPLETED:
            progress.status = OnboardingTrainingStatus.COMPLETED
            progress.completed_at = now
            progress = self.repository.save_progress(progress)

        self._complete_matching_onboarding_assignment(employee.id, training_id, now)

        return MyTrainingResourceResponse(
            training_id=training.id,
            title=training.title,
            description=training.description,
            resource_url=training.resource_url,
            status=OnboardingTrainingStatus.COMPLETED,
            completed_at=progress.completed_at,
            created_at=training.created_at,
            updated_at=training.updated_at,
        )

    def complete_assignment_for_user(self, user_id: int, assignment_id: int) -> OnboardingTraining:
        onboarding = self._require_onboarding_for_user(user_id)
        assignment = self.repository.get_assignment_for_onboarding(assignment_id, onboarding.id)
        if assignment is None:
            raise AppException("Training assignment not found", status_code=404)
        if assignment.status == OnboardingTrainingStatus.COMPLETED:
            # Idempotent: opening a resource again should not fail.
            self._ensure_employee_progress_completed(
                onboarding.employee_id, assignment.training_id, assignment.completed_at
            )
            return assignment
        now = datetime.now(UTC)
        assignment.status = OnboardingTrainingStatus.COMPLETED
        assignment.completed_at = now
        saved = self.repository.save_assignment(assignment)
        self._ensure_employee_progress_completed(
            onboarding.employee_id, assignment.training_id, now
        )
        sync_onboarding_tasks_for_employee(
            self.repository.db,
            onboarding.employee_id,
            task_types={OnboardingTaskType.TRAINING},
        )
        return saved

    def _complete_matching_onboarding_assignment(
        self, employee_id: int, training_id: int, completed_at: datetime
    ) -> None:
        onboarding = self.onboardings.get_by_employee_id(employee_id)
        if onboarding is None:
            return
        assignment = self.repository.find_assignment(onboarding.id, training_id)
        if assignment is None:
            return
        if assignment.status != OnboardingTrainingStatus.COMPLETED:
            assignment.status = OnboardingTrainingStatus.COMPLETED
            assignment.completed_at = completed_at
            self.repository.save_assignment(assignment)
            sync_onboarding_tasks_for_employee(
                self.repository.db,
                employee_id,
                task_types={OnboardingTaskType.TRAINING},
            )

    def _ensure_employee_progress_completed(
        self,
        employee_id: int,
        training_id: int,
        completed_at: datetime | None,
    ) -> None:
        now = completed_at or datetime.now(UTC)
        progress = self.repository.get_progress(employee_id, training_id)
        if progress is None:
            self.repository.add_progress(
                EmployeeTrainingProgress(
                    employee_id=employee_id,
                    training_id=training_id,
                    status=OnboardingTrainingStatus.COMPLETED,
                    completed_at=now,
                )
            )
            return
        if progress.status != OnboardingTrainingStatus.COMPLETED:
            progress.status = OnboardingTrainingStatus.COMPLETED
            progress.completed_at = now
            self.repository.save_progress(progress)

    def _onboarding_for_user(self, user_id: int):
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            return None
        return self.onboardings.get_by_employee_id(employee.id)

    def _require_onboarding_for_user(self, user_id: int):
        onboarding = self._onboarding_for_user(user_id)
        if onboarding is None:
            raise AppException("Onboarding not found", status_code=404)
        return onboarding

    def _notify_training_assigned(self, assignment: OnboardingTraining, training: Training) -> None:
        if self.notifications is None:
            return
        onboarding = self.onboardings.get_by_id(assignment.onboarding_id)
        if onboarding is None:
            return
        employee = self.employees.get_by_id(onboarding.employee_id)
        if employee is None or employee.user_id is None:
            return
        self.notifications.create_if_absent(
            recipient_user_id=employee.user_id,
            type=NotificationType.ONBOARDING_TRAINING_ASSIGNED,
            title="New training assigned",
            message=f'You have been assigned a new training: "{training.title}".',
            related_entity_type="onboarding_training",
            related_entity_id=assignment.id,
        )

    def _notify_training_resource_published(self, training: Training) -> None:
        if self.notifications is None:
            return
        title = "New training resource"
        message = (
            f'A new training resource is available: "{training.title}". '
            "Open Training to view it."
        )
        for user_id in self.employees.list_active_user_ids():
            self.notifications.create_if_absent(
                recipient_user_id=user_id,
                type=NotificationType.TRAINING_RESOURCE_PUBLISHED,
                title=title,
                message=message,
                related_entity_type="training",
                related_entity_id=training.id,
            )


def build_training_response(training: Training) -> TrainingResponse:
    return TrainingResponse.model_validate(training)


def build_assignment_response(assignment: OnboardingTraining) -> OnboardingTrainingResponse:
    return OnboardingTrainingResponse(
        id=assignment.id,
        onboarding_id=assignment.onboarding_id,
        training_id=assignment.training_id,
        status=assignment.status,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        title=assignment.training.title,
        description=assignment.training.description,
        resource_url=assignment.training.resource_url,
    )
