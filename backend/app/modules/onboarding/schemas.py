from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.onboarding.models import OnboardingStatus, OnboardingTaskStatus


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
    title: str
    description: str | None
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


class OnboardingTaskUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    status: OnboardingTaskStatus | None = None


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
    trainings: ProgressCountResponse
    documents: DocumentCountResponse
    overall_percentage: int
