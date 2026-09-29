from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.offboarding.models import (
    OffboardingReason,
    OffboardingStatus,
    OffboardingTaskCategory,
    OffboardingTaskStatus,
)


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


class OffboardingTaskCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: OffboardingTaskCategory
    is_required: bool = True
    assigned_to_employee_id: int | None = None
    due_date: date | None = None


class OffboardingTaskUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: OffboardingTaskCategory | None = None
    is_required: bool | None = None
    assigned_to_employee_id: int | None = None
    due_date: date | None = None
    clear_assignee: bool = False
    clear_due_date: bool = False


class OffboardingTaskAssigneeSummary(BaseModel):
    id: int
    full_name: str
    email: str


class OffboardingTaskResponse(BaseModel):
    id: int
    offboarding_case_id: int
    title: str
    description: str | None
    category: OffboardingTaskCategory
    status: OffboardingTaskStatus
    is_required: bool
    assigned_to_employee_id: int | None
    assigned_to: OffboardingTaskAssigneeSummary | None
    due_date: date | None
    is_overdue: bool
    completed_at: datetime | None
    completed_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class OffboardingTaskEmployeeViewResponse(BaseModel):
    id: int
    offboarding_case_id: int
    title: str
    description: str | None
    category: OffboardingTaskCategory
    status: OffboardingTaskStatus
    is_required: bool
    due_date: date | None
    is_overdue: bool
    completed_at: datetime | None


class OffboardingProgressResponse(BaseModel):
    offboarding_case_id: int
    total_tasks: int
    completed_tasks: int
    skipped_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    required_total: int
    required_completed: int
    percentage: int
    required_complete: bool
    overdue_tasks: int
