from dataclasses import dataclass

from app.modules.documents.models import DocumentType
from app.modules.documents.service import DocumentService
from app.modules.onboarding.models import OnboardingTask, OnboardingTaskType
from app.modules.profile.service import ProfileService
from app.modules.training.models import OnboardingTrainingStatus
from app.modules.training.repository import TrainingRepository


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    reason: str | None = None


class OnboardingTaskVerificationService:
    """Determines whether an onboarding task is satisfied by real business state."""

    def __init__(
        self,
        profile: ProfileService | None = None,
        documents: DocumentService | None = None,
        trainings: TrainingRepository | None = None,
    ):
        self.profile = profile
        self.documents = documents
        self.trainings = trainings

    def verify_task(self, employee_id: int, task: OnboardingTask) -> VerificationResult:
        if task.task_type in {
            OnboardingTaskType.MANUAL,
            OnboardingTaskType.ACKNOWLEDGEMENT,
        }:
            return VerificationResult(
                verified=False,
                reason="Task requires explicit employee or HR completion",
            )

        if task.task_type == OnboardingTaskType.PROFILE_PERSONAL_INFO:
            if self.profile is None:
                return VerificationResult(verified=False, reason="Profile service unavailable")
            if self.profile.is_personal_information_complete(employee_id):
                return VerificationResult(verified=True)
            return VerificationResult(
                verified=False,
                reason="Required personal information is incomplete",
            )

        if task.task_type == OnboardingTaskType.PROFILE_PICTURE:
            if self.profile is None:
                return VerificationResult(verified=False, reason="Profile service unavailable")
            if self.profile.has_profile_picture(employee_id):
                return VerificationResult(verified=True)
            return VerificationResult(verified=False, reason="Profile picture is missing")

        if task.task_type == OnboardingTaskType.EDUCATION:
            if self.profile is None:
                return VerificationResult(verified=False, reason="Profile service unavailable")
            if self.profile.has_education(employee_id):
                return VerificationResult(verified=True)
            return VerificationResult(verified=False, reason="No education records")

        if task.task_type == OnboardingTaskType.EXPERIENCE:
            if self.profile is None:
                return VerificationResult(verified=False, reason="Profile service unavailable")
            if self.profile.has_experience(employee_id):
                return VerificationResult(verified=True)
            return VerificationResult(verified=False, reason="No experience records")

        if task.task_type == OnboardingTaskType.DOCUMENT:
            if self.documents is None:
                return VerificationResult(verified=False, reason="Document service unavailable")
            if task.document_type is None:
                return VerificationResult(
                    verified=False,
                    reason="Document task has no required document_type",
                )
            if self.documents.has_document_of_type(employee_id, task.document_type):
                return VerificationResult(verified=True)
            return VerificationResult(
                verified=False,
                reason=f"Required document type missing: {task.document_type.value}",
            )

        if task.task_type == OnboardingTaskType.TRAINING:
            if self.trainings is None:
                return VerificationResult(verified=False, reason="Training repository unavailable")
            if task.training_id is None:
                return VerificationResult(
                    verified=False,
                    reason="Training task has no required training_id",
                )
            assignment = self.trainings.find_assignment(task.onboarding_id, task.training_id)
            if assignment is not None and assignment.status == OnboardingTrainingStatus.COMPLETED:
                return VerificationResult(verified=True)
            return VerificationResult(
                verified=False,
                reason="Required training assignment is not completed",
            )

        return VerificationResult(verified=False, reason="Unknown task type")
