from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.offboarding.models import OffboardingReason, OffboardingStatus


class OffboardingCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    reason: OffboardingReason
    reason_details: str | None = Field(default=None, max_length=2000)
    last_working_day: date


class OffboardingEmployeeSummary(BaseModel):
    id: int
    full_name: str
    email: str
    position: str
    employee_number: str


class OffboardingCreatedBySummary(BaseModel):
    id: int
    full_name: str
    email: str


class OffboardingListItemResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    employee_email: str
    position: str
    reason: OffboardingReason
    last_working_day: date
    status: OffboardingStatus
    initiated_at: datetime


class OffboardingDetailResponse(BaseModel):
    id: int
    employee_id: int
    employee: OffboardingEmployeeSummary
    reason: OffboardingReason
    reason_details: str | None
    last_working_day: date
    status: OffboardingStatus
    initiated_at: datetime
    completed_at: datetime | None
    created_by: OffboardingCreatedBySummary | None
    created_at: datetime
    updated_at: datetime


class OffboardingEmployeeViewResponse(BaseModel):
    id: int
    status: OffboardingStatus
    reason: OffboardingReason
    last_working_day: date
    initiated_at: datetime
    completed_at: datetime | None
