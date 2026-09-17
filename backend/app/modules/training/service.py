from datetime import UTC, datetime

from app.modules.employees.repository import EmployeeRepository
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.training.models import OnboardingTraining, OnboardingTrainingStatus, Training
from app.modules.training.repository import TrainingRepository
from app.modules.training.schemas import (
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
    ):
        self.repository = repository
        self.onboardings = onboardings
        self.employees = employees

    def list_trainings(self) -> list[Training]:
        return self.repository.list_trainings()

    def create_training(self, payload: TrainingCreateRequest) -> Training:
        description = payload.description.strip() if payload.description else None
        if description == "":
            description = None
        training = Training(title=payload.title.strip(), description=description)
        return self.repository.add_training(training)

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
        return self.repository.add_assignment(assignment)

    def remove_assignment(self, onboarding_id: int, assignment_id: int) -> None:
        if self.onboardings.get_by_id(onboarding_id) is None:
            raise AppException("Onboarding not found", status_code=404)
        assignment = self.repository.get_assignment_for_onboarding(assignment_id, onboarding_id)
        if assignment is None:
            raise AppException("Training assignment not found", status_code=404)
        self.repository.delete_assignment(assignment)

    def list_assignments_for_user(self, user_id: int) -> list[OnboardingTraining]:
        onboarding = self._require_onboarding_for_user(user_id)
        return self.repository.list_assignments(onboarding.id)

    def complete_assignment_for_user(self, user_id: int, assignment_id: int) -> OnboardingTraining:
        onboarding = self._require_onboarding_for_user(user_id)
        assignment = self.repository.get_assignment_for_onboarding(assignment_id, onboarding.id)
        if assignment is None:
            raise AppException("Training assignment not found", status_code=404)
        if assignment.status == OnboardingTrainingStatus.COMPLETED:
            raise AppException("Training is already completed", status_code=400)
        assignment.status = OnboardingTrainingStatus.COMPLETED
        assignment.completed_at = datetime.now(UTC)
        return self.repository.save_assignment(assignment)

    def _require_onboarding_for_user(self, user_id: int):
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Onboarding not found", status_code=404)
        onboarding = self.onboardings.get_by_employee_id(employee.id)
        if onboarding is None:
            raise AppException("Onboarding not found", status_code=404)
        return onboarding


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
    )
