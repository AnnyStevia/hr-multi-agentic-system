from datetime import UTC, datetime

from app.modules.documents.models import DocumentType
from app.modules.documents.repository import DocumentRepository
from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.hr_access import list_hr_staff_user_ids
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.models import (
    Onboarding,
    OnboardingStatus,
    OnboardingTask,
    OnboardingTaskStatus,
    OnboardingTaskTemplate,
    OnboardingTaskType,
)
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schemas import (
    DocumentCountResponse,
    OnboardingListItemResponse,
    OnboardingProgressResponse,
    OnboardingResponse,
    OnboardingTaskCreateRequest,
    OnboardingTaskResponse,
    OnboardingTaskTemplateCreateRequest,
    OnboardingTaskTemplateResponse,
    OnboardingTaskTemplateUpdateRequest,
    OnboardingTaskUpdateRequest,
    ProgressCountResponse,
)
from app.modules.onboarding.verification import OnboardingTaskVerificationService
from app.modules.training.models import OnboardingTraining, OnboardingTrainingStatus
from app.modules.training.repository import TrainingRepository
from app.shared.exceptions import AppException

AUTO_VERIFIABLE_TYPES = frozenset(
    {
        OnboardingTaskType.PROFILE_PERSONAL_INFO,
        OnboardingTaskType.PROFILE_PICTURE,
        OnboardingTaskType.EDUCATION,
        OnboardingTaskType.EXPERIENCE,
        OnboardingTaskType.DOCUMENT,
        OnboardingTaskType.TRAINING,
    }
)


class OnboardingService:
    def __init__(
        self,
        repository: OnboardingRepository,
        employees: EmployeeRepository,
        notifications: NotificationService | None = None,
        documents: DocumentRepository | None = None,
        trainings: TrainingRepository | None = None,
        verification: OnboardingTaskVerificationService | None = None,
    ):
        self.repository = repository
        self.employees = employees
        self.notifications = notifications
        self.documents = documents
        self.trainings = trainings
        self.verification = verification or OnboardingTaskVerificationService()

    def create_for_employee(self, employee_id: int, *, commit: bool = True) -> Onboarding:
        if self.repository.get_by_employee_id(employee_id) is not None:
            raise AppException(
                "An onboarding record already exists for this employee",
                status_code=409,
            )
        onboarding = self.repository.add(self._new_onboarding(employee_id), commit=False)
        self._assign_active_templates(onboarding, commit=False)
        if commit:
            self.repository.db.commit()
            self.repository.db.refresh(onboarding)
        return onboarding

    def backfill_missing_onboardings(self, *, commit: bool = True) -> int:
        employee_ids = self.repository.list_employee_ids_without_onboarding()
        created = 0
        for employee_id in employee_ids:
            self.repository.add(self._new_onboarding(employee_id), commit=False)
            created += 1
        if commit and created:
            self.repository.db.commit()
        return created

    def _assign_active_templates(self, onboarding: Onboarding, *, commit: bool = False) -> int:
        assigned = 0
        for template in self.repository.list_active_templates():
            if self.repository.has_task_for_template(onboarding.id, template.id):
                continue
            task = OnboardingTask(
                onboarding_id=onboarding.id,
                template_id=template.id,
                title=template.title,
                description=template.description,
                task_type=template.task_type,
                is_required=template.is_required,
                document_type=template.document_type,
                training_id=template.training_id,
                status=OnboardingTaskStatus.PENDING,
            )
            self.repository.add_task(task, commit=False)
            if (
                template.task_type == OnboardingTaskType.TRAINING
                and template.training_id is not None
                and self.trainings is not None
                and self.trainings.find_assignment(onboarding.id, template.training_id) is None
            ):
                self.repository.db.add(
                    OnboardingTraining(
                        onboarding_id=onboarding.id,
                        training_id=template.training_id,
                        status=OnboardingTrainingStatus.PENDING,
                        assigned_at=datetime.now(UTC),
                    )
                )
            assigned += 1
        if commit and assigned:
            self.repository.db.commit()
        return assigned

    @staticmethod
    def _new_onboarding(employee_id: int) -> Onboarding:
        return Onboarding(
            employee_id=employee_id,
            status=OnboardingStatus.IN_PROGRESS,
            started_at=datetime.now(UTC),
        )

    def list_templates(self, *, active_only: bool = False) -> list[OnboardingTaskTemplate]:
        return self.repository.list_templates(active_only=active_only)

    def get_template(self, template_id: int) -> OnboardingTaskTemplate:
        template = self.repository.get_template_by_id(template_id)
        if template is None:
            raise AppException("Onboarding task template not found", status_code=404)
        return template

    def create_template(
        self, payload: OnboardingTaskTemplateCreateRequest
    ) -> OnboardingTaskTemplate:
        title = payload.title.strip()
        if not title:
            raise AppException("Title is required", status_code=400)
        if self.repository.get_template_by_title(title) is not None:
            raise AppException("A template with this title already exists", status_code=409)
        description = payload.description.strip() if payload.description else None
        if description == "":
            description = None
        document_type, training_id = self._normalize_task_config(
            payload.task_type, payload.document_type, payload.training_id
        )
        return self.repository.add_template(
            OnboardingTaskTemplate(
                title=title,
                description=description,
                task_type=payload.task_type,
                is_required=payload.is_required,
                is_active=payload.is_active,
                document_type=document_type,
                training_id=training_id,
            )
        )

    def update_template(
        self, template_id: int, payload: OnboardingTaskTemplateUpdateRequest
    ) -> OnboardingTaskTemplate:
        template = self.get_template(template_id)
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            title = data["title"].strip()
            if not title:
                raise AppException("Title is required", status_code=400)
            existing = self.repository.get_template_by_title(title)
            if existing is not None and existing.id != template.id:
                raise AppException("A template with this title already exists", status_code=409)
            template.title = title
        if "description" in data:
            description = data["description"]
            if description is not None:
                description = description.strip() or None
            template.description = description
        if "task_type" in data and data["task_type"] is not None:
            template.task_type = data["task_type"]
        if "is_required" in data and data["is_required"] is not None:
            template.is_required = data["is_required"]
        if "is_active" in data and data["is_active"] is not None:
            template.is_active = data["is_active"]
        if "document_type" in data or "training_id" in data or "task_type" in data:
            next_type = data.get("task_type", template.task_type)
            next_doc = data["document_type"] if "document_type" in data else template.document_type
            next_train = data["training_id"] if "training_id" in data else template.training_id
            document_type, training_id = self._normalize_task_config(next_type, next_doc, next_train)
            template.document_type = document_type
            template.training_id = training_id
        return self.repository.save_template(template)

    def delete_template(self, template_id: int) -> OnboardingTaskTemplate | None:
        """Hard-delete unused templates; soft-deactivate when already assigned."""
        template = self.get_template(template_id)
        if self.repository.count_tasks_for_template(template_id) > 0:
            template.is_active = False
            return self.repository.save_template(template)
        self.repository.delete_template(template)
        return None

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
        saved = self.repository.save(onboarding)
        employee = self.employees.get_by_id(saved.employee_id)
        if employee is not None:
            self._notify_onboarding_completed(saved, employee)
        return saved

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
        document_type, training_id = self._normalize_task_config(
            payload.task_type, payload.document_type, payload.training_id
        )
        task = OnboardingTask(
            onboarding_id=onboarding_id,
            title=payload.title.strip(),
            description=description,
            task_type=payload.task_type,
            is_required=payload.is_required,
            document_type=document_type,
            training_id=training_id,
            status=OnboardingTaskStatus.PENDING,
            due_date=payload.due_date,
        )
        saved = self.repository.add_task(task)
        if (
            saved.task_type == OnboardingTaskType.TRAINING
            and saved.training_id is not None
            and self.trainings is not None
            and self.trainings.find_assignment(onboarding.id, saved.training_id) is None
        ):
            self.trainings.add_assignment(
                OnboardingTraining(
                    onboarding_id=onboarding.id,
                    training_id=saved.training_id,
                    status=OnboardingTrainingStatus.PENDING,
                    assigned_at=datetime.now(UTC),
                )
            )
        self._notify_task_assigned(onboarding, saved)
        return saved

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
        if "task_type" in data and data["task_type"] is not None:
            task.task_type = data["task_type"]
        if "is_required" in data and data["is_required"] is not None:
            task.is_required = data["is_required"]
        if "document_type" in data or "training_id" in data or "task_type" in data:
            next_type = data.get("task_type", task.task_type)
            next_doc = data["document_type"] if "document_type" in data else task.document_type
            next_train = data["training_id"] if "training_id" in data else task.training_id
            document_type, training_id = self._normalize_task_config(next_type, next_doc, next_train)
            task.document_type = document_type
            task.training_id = training_id
        if "status" in data and data["status"] is not None:
            new_status = data["status"]
            if new_status == OnboardingTaskStatus.COMPLETED:
                if task.task_type != OnboardingTaskType.MANUAL:
                    raise AppException(
                        "Only manual tasks can be marked completed by HR this way",
                        status_code=400,
                    )
                if task.status != OnboardingTaskStatus.COMPLETED:
                    task.status = OnboardingTaskStatus.COMPLETED
                    if task.completed_at is None:
                        task.completed_at = datetime.now(UTC)
            elif new_status == OnboardingTaskStatus.PENDING:
                if task.task_type != OnboardingTaskType.MANUAL:
                    raise AppException(
                        "Only manual tasks can have status changed this way",
                        status_code=400,
                    )
                task.status = OnboardingTaskStatus.PENDING
                task.completed_at = None

        saved = self.repository.save_task(task)
        if saved.status == OnboardingTaskStatus.COMPLETED:
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
        """Deprecated path: only acknowledgement is allowed; prefer acknowledge_task_for_employee."""
        return self.acknowledge_task_for_employee(user_id, task_id)

    def acknowledge_task_for_employee(self, user_id: int, task_id: int) -> OnboardingTask:
        task = self.repository.get_task_by_id(task_id)
        if task is None:
            raise AppException("Onboarding task not found", status_code=404)

        employee = self.employees.get_by_id(task.onboarding.employee_id)
        if employee is None or employee.user_id != user_id:
            raise AppException("Onboarding task not found", status_code=404)

        if task.task_type != OnboardingTaskType.ACKNOWLEDGEMENT:
            raise AppException(
                "Only acknowledgement tasks can be acknowledged by the employee",
                status_code=400,
            )
        if task.status == OnboardingTaskStatus.COMPLETED:
            raise AppException("Task is already completed", status_code=400)

        task.status = OnboardingTaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        saved = self.repository.save_task(task)
        self._maybe_complete_onboarding(saved.onboarding_id)
        return saved

    def complete_manual_task_for_hr(self, task_id: int) -> OnboardingTask:
        task = self.repository.get_task_by_id(task_id)
        if task is None:
            raise AppException("Onboarding task not found", status_code=404)
        if task.task_type != OnboardingTaskType.MANUAL:
            raise AppException(
                "Only manual tasks can be completed by HR this way",
                status_code=400,
            )
        if task.status == OnboardingTaskStatus.COMPLETED:
            raise AppException("Task is already completed", status_code=400)

        task.status = OnboardingTaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        saved = self.repository.save_task(task)
        self._maybe_complete_onboarding(saved.onboarding_id)
        return saved

    def sync_verified_tasks(
        self,
        employee_id: int,
        *,
        task_types: set[OnboardingTaskType] | None = None,
    ) -> None:
        onboarding = self.repository.get_by_employee_id(employee_id)
        if onboarding is None or onboarding.status == OnboardingStatus.COMPLETED:
            return

        types = task_types or AUTO_VERIFIABLE_TYPES
        tasks = self.repository.list_tasks_by_onboarding_id(onboarding.id)
        changed = False
        for task in tasks:
            if task.task_type not in AUTO_VERIFIABLE_TYPES:
                continue
            if task.task_type not in types:
                continue
            result = self.verification.verify_task(employee_id, task)
            if result.verified:
                if task.status != OnboardingTaskStatus.COMPLETED:
                    task.status = OnboardingTaskStatus.COMPLETED
                    task.completed_at = datetime.now(UTC)
                    self.repository.save_task(task)
                    changed = True
            elif task.status == OnboardingTaskStatus.COMPLETED:
                task.status = OnboardingTaskStatus.PENDING
                task.completed_at = None
                self.repository.save_task(task)
                changed = True

        if changed:
            self._maybe_complete_onboarding(onboarding.id)

    def _normalize_task_config(
        self,
        task_type: OnboardingTaskType,
        document_type: DocumentType | None,
        training_id: int | None,
    ) -> tuple[DocumentType | None, int | None]:
        if task_type == OnboardingTaskType.DOCUMENT:
            if document_type is None:
                raise AppException(
                    "document_type is required for document tasks",
                    status_code=400,
                )
            if training_id is not None:
                raise AppException(
                    "training_id is only allowed for training tasks",
                    status_code=400,
                )
            return document_type, None
        if task_type == OnboardingTaskType.TRAINING:
            if training_id is None:
                raise AppException(
                    "training_id is required for training tasks",
                    status_code=400,
                )
            if self.trainings is None or self.trainings.get_training(training_id) is None:
                raise AppException("Training not found", status_code=404)
            if document_type is not None:
                raise AppException(
                    "document_type is only allowed for document tasks",
                    status_code=400,
                )
            return None, training_id
        if document_type is not None or training_id is not None:
            raise AppException(
                "document_type and training_id are only valid for document/training tasks",
                status_code=400,
            )
        return None, None

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
        required = [task for task in tasks if task.is_required]
        if not required:
            return
        if any(task.status != OnboardingTaskStatus.COMPLETED for task in required):
            return
        onboarding.status = OnboardingStatus.COMPLETED
        onboarding.completed_at = datetime.now(UTC)
        saved = self.repository.save(onboarding)
        employee = self.employees.get_by_id(saved.employee_id)
        if employee is not None:
            self._notify_onboarding_completed(saved, employee)

    def get_progress_for_hr(self, onboarding_id: int) -> OnboardingProgressResponse:
        onboarding = self.get_for_hr(onboarding_id)
        self._maybe_complete_onboarding(onboarding.id)
        onboarding = self.get_for_hr(onboarding_id)
        return self._build_progress(onboarding)

    def get_progress_for_employee_user(self, user_id: int) -> OnboardingProgressResponse:
        onboarding = self.get_for_employee_user(user_id)
        self._maybe_complete_onboarding(onboarding.id)
        onboarding = self.get_for_employee_user(user_id)
        return self._build_progress(onboarding)

    def _build_progress(self, onboarding: Onboarding) -> OnboardingProgressResponse:
        tasks = self.repository.list_tasks_by_onboarding_id(onboarding.id)
        task_total = len(tasks)
        task_completed = sum(1 for task in tasks if task.status == OnboardingTaskStatus.COMPLETED)
        task_pending = task_total - task_completed

        required = [task for task in tasks if task.is_required]
        optional = [task for task in tasks if not task.is_required]
        required_completed = sum(
            1 for task in required if task.status == OnboardingTaskStatus.COMPLETED
        )
        optional_completed = sum(
            1 for task in optional if task.status == OnboardingTaskStatus.COMPLETED
        )

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

        # Overall % uses required tasks + trainings (completion gate is required tasks)
        denominator = len(required) + training_total
        if denominator == 0:
            overall_percentage = 0
        else:
            overall_percentage = round(
                (required_completed + training_completed) / denominator * 100
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
            required_tasks=ProgressCountResponse(
                total=len(required),
                completed=required_completed,
                pending=len(required) - required_completed,
            ),
            optional_tasks=ProgressCountResponse(
                total=len(optional),
                completed=optional_completed,
                pending=len(optional) - optional_completed,
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


def build_template_response(template: OnboardingTaskTemplate) -> OnboardingTaskTemplateResponse:
    return OnboardingTaskTemplateResponse.model_validate(template)
