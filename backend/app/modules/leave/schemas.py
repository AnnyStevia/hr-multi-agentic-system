from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.modules.leave.models import (
    LeaveApprovalStatus,
    LeaveCancellationStatus,
    LeaveRequestStatus,
)


class LeaveTypeCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    is_paid: bool = True
    is_active: bool = True


class LeaveTypeUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    is_paid: bool | None = None
    is_active: bool | None = None


class LeaveTypeResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_paid: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeavePolicyCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int
    year: int = Field(ge=2000, le=2100)
    days_allowed: int = Field(ge=0, le=365)


class LeavePolicyUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    year: int | None = Field(default=None, ge=2000, le=2100)
    days_allowed: int | None = Field(default=None, ge=0, le=365)


class LeavePolicyResponse(BaseModel):
    id: int
    leave_type_id: int
    leave_type_name: str
    year: int
    days_allowed: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeaveBalanceResponse(BaseModel):
    employee_id: int
    leave_type_id: int
    leave_type_name: str
    year: int
    days_allowed: int
    days_used: int
    days_pending: int
    days_available: int


class LeaveRequestCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int
    start_date: date
    end_date: date
    reason: str | None = None


class LeaveRequestRejectRequest(BaseModel):
    model_config = {"extra": "forbid"}

    rejection_reason: str = Field(min_length=1, max_length=2000)


class LeaveCancellationRequest(BaseModel):
    model_config = {"extra": "forbid"}

    reason: str = Field(min_length=1, max_length=2000)


class LeaveCancellationRejectRequest(BaseModel):
    model_config = {"extra": "forbid"}

    reason: str = Field(min_length=1, max_length=2000)


class LeaveRequestResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    leave_type_id: int
    leave_type_name: str
    start_date: date
    end_date: date
    requested_days: int
    reason: str | None
    rejection_reason: str | None = None
    status: LeaveRequestStatus
    approved_at: datetime | None
    rejected_at: datetime | None
    reviewed_by: int | None
    manager_approval: LeaveApprovalStatus
    manager_approved_by: int | None = None
    manager_approved_at: datetime | None = None
    hr_approval: LeaveApprovalStatus
    hr_approved_by: int | None = None
    hr_approved_at: datetime | None = None
    admin_override: LeaveApprovalStatus
    admin_approved_by: int | None = None
    admin_approved_at: datetime | None = None
    cancellation_status: LeaveCancellationStatus = LeaveCancellationStatus.NONE
    cancellation_requested_at: datetime | None = None
    cancellation_requested_by: int | None = None
    cancellation_reason: str | None = None
    cancellation_processed_at: datetime | None = None
    cancellation_processed_by: int | None = None
    cancellation_rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeaveCalendarPeriod(BaseModel):
    request_id: int
    leave_type_name: str
    status: LeaveRequestStatus
    start_date: date
    end_date: date


class LeaveCalendarResponse(BaseModel):
    year: int
    month: int
    periods: list[LeaveCalendarPeriod]


class CurrentLeaveSummary(BaseModel):
    leave_type: str
    start_date: date
    end_date: date


class CurrentWorkStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"


class CurrentWorkStatusPayload(BaseModel):
    current_work_status: CurrentWorkStatus
    current_leave: CurrentLeaveSummary | None = None
