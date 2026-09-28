from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from app.modules.training.models import OnboardingTrainingStatus


def _normalize_resource_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("resource_url must be a valid http or https URL")
    return cleaned


class TrainingCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    resource_url: str | None = Field(default=None, max_length=2048)

    @field_validator("resource_url")
    @classmethod
    def validate_resource_url(cls, value: str | None) -> str | None:
        return _normalize_resource_url(value)


class TrainingUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    resource_url: str | None = Field(default=None, max_length=2048)

    @field_validator("resource_url")
    @classmethod
    def validate_resource_url(cls, value: str | None) -> str | None:
        return _normalize_resource_url(value)


class TrainingResponse(BaseModel):
    id: int
    title: str
    description: str | None
    resource_url: str | None = None
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
    resource_url: str | None = None

    model_config = {"from_attributes": True}
