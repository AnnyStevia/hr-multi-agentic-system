from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.documents.models import DocumentType
from app.modules.onboarding.models import (
    OnboardingStatus,
    OnboardingTaskStatus,
    OnboardingTaskType,
)


class OnboardingResponse(BaseModel):
    id: int
    employee_id: int
    status: OnboardingStatus
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnboardingListItemResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    position: str
    status: OnboardingStatus
    started_at: datetime
    completed_at: datetime | None
    completed_tasks_count: int
    total_tasks_count: int


class OnboardingTaskResponse(BaseModel):
    id: int
    onboarding_id: int
    template_id: int | None = None
    title: str
    description: str | None
    task_type: OnboardingTaskType = OnboardingTaskType.MANUAL
    is_required: bool = True
    document_type: DocumentType | None = None
    training_id: int | None = None
    status: OnboardingTaskStatus
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnboardingTaskCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    task_type: OnboardingTaskType = OnboardingTaskType.MANUAL
    is_required: bool = True
    document_type: DocumentType | None = None
    training_id: int | None = None


class OnboardingTaskUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    status: OnboardingTaskStatus | None = None
    task_type: OnboardingTaskType | None = None
    is_required: bool | None = None
    document_type: DocumentType | None = None
    training_id: int | None = None


class ProgressCountResponse(BaseModel):
    total: int
    completed: int
    pending: int


class DocumentCountResponse(BaseModel):
    total: int


class OnboardingProgressResponse(BaseModel):
    onboarding_id: int
    status: OnboardingStatus
    completed_at: datetime | None
    tasks: ProgressCountResponse
    required_tasks: ProgressCountResponse
    optional_tasks: ProgressCountResponse
    trainings: ProgressCountResponse
    documents: DocumentCountResponse
    overall_percentage: int


class OnboardingTaskTemplateCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    task_type: OnboardingTaskType
    is_required: bool = True
    is_active: bool = True
    document_type: DocumentType | None = None
    training_id: int | None = None


class OnboardingTaskTemplateUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    task_type: OnboardingTaskType | None = None
    is_required: bool | None = None
    is_active: bool | None = None
    document_type: DocumentType | None = None
    training_id: int | None = None


class OnboardingTaskTemplateResponse(BaseModel):
    id: int
    title: str
    description: str | None
    task_type: OnboardingTaskType
    is_required: bool
    is_active: bool
    document_type: DocumentType | None = None
    training_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
