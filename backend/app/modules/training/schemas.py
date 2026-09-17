from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.training.models import OnboardingTrainingStatus


class TrainingCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class TrainingUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class TrainingResponse(BaseModel):
    id: int
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnboardingTrainingAssignRequest(BaseModel):
    model_config = {"extra": "forbid"}

    training_id: int


class OnboardingTrainingResponse(BaseModel):
    id: int
    onboarding_id: int
    training_id: int
    status: OnboardingTrainingStatus
    assigned_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    title: str
    description: str | None

    model_config = {"from_attributes": True}
