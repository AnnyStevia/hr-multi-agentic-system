from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.offboarding.models import OffboardingReason
from app.modules.offboarding_requests.models import OffboardingRequestStatus


EmployeeOffboardingRequestReason = Literal[
    "resignation",
    "end_of_contract",
    "retirement",
    "other",
]


class OffboardingRequestCreatePayload(BaseModel):
    model_config = {"extra": "forbid"}

    reason: EmployeeOffboardingRequestReason
    reason_details: str | None = Field(default=None, max_length=2000)
    requested_last_working_day: date


class OffboardingRequestRejectPayload(BaseModel):
    model_config = {"extra": "forbid"}

    rejection_reason: str | None = Field(default=None, max_length=2000)


class OffboardingRequestLinkCasePayload(BaseModel):
    model_config = {"extra": "forbid"}

    offboarding_case_id: int


class OffboardingRequestEmployeeSummary(BaseModel):
    id: int
    full_name: str
    email: str
    position: str
    employee_number: str


class OffboardingRequestReviewedBySummary(BaseModel):
    id: int
    full_name: str
    email: str


class OffboardingRequestListItemResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    employee_email: str
    position: str
    reason: OffboardingReason
    requested_last_working_day: date
    status: OffboardingRequestStatus
    submitted_at: datetime
    offboarding_case_id: int | None


class OffboardingRequestDetailResponse(BaseModel):
    id: int
    employee_id: int
    employee: OffboardingRequestEmployeeSummary
    reason: OffboardingReason
    reason_details: str | None
    requested_last_working_day: date
    status: OffboardingRequestStatus
    submitted_at: datetime
    reviewed_by: OffboardingRequestReviewedBySummary | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    offboarding_case_id: int | None
    created_at: datetime
    updated_at: datetime


class OffboardingRequestEmployeeViewResponse(BaseModel):
    id: int
    reason: OffboardingReason
    reason_details: str | None
    requested_last_working_day: date
    status: OffboardingRequestStatus
    submitted_at: datetime
    reviewed_at: datetime | None
    rejection_reason: str | None
    offboarding_case_id: int | None
