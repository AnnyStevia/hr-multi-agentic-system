from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.interviews.models import InterviewOutcome


class InterviewSlotInput(BaseModel):
    model_config = {"extra": "forbid"}

    starts_at: datetime
    ends_at: datetime


class InterviewCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1, max_length=5000)
    slots: list[InterviewSlotInput] = Field(min_length=2, max_length=5)
    interviewer_employee_ids: list[int] = Field(min_length=1, max_length=20)


class InterviewSlotResponse(BaseModel):
    id: int
    starts_at: datetime
    ends_at: datetime
    is_selected: bool
    is_available: bool


class InterviewerSummary(BaseModel):
    employee_id: int
    full_name: str
    position: str | None = None


class InterviewSummary(BaseModel):
    id: int
    application_id: int
    status: str
    status_label: str
    message: str
    created_at: datetime
    job_title: str
    candidate_name: str
    interviewer_name: str | None
    interviewers: list[InterviewerSummary] = Field(default_factory=list)
    selected_slot: InterviewSlotResponse | None = None
    feedback: str | None = None
    completed_at: datetime | None = None
    outcome: str | None = None
    outcome_label: str | None = None
    hired_employee_id: int | None = None
    meeting_url: str | None = None


class InterviewDetailResponse(BaseModel):
    id: int
    application_id: int
    status: str
    message: str
    created_at: datetime
    updated_at: datetime
    job_title: str
    candidate_name: str
    interviewer_name: str | None
    interviewers: list[InterviewerSummary] = Field(default_factory=list)
    slots: list[InterviewSlotResponse]
    selected_slot: InterviewSlotResponse | None = None
    feedback: str | None = None
    completed_at: datetime | None = None
    outcome: str | None = None
    outcome_label: str | None = None
    hired_employee_id: int | None = None
    meeting_url: str | None = None


class InterviewConfirmRequest(BaseModel):
    model_config = {"extra": "forbid"}

    slot_id: int


class InterviewCompleteRequest(BaseModel):
    model_config = {"extra": "forbid"}

    feedback: str = Field(min_length=1, max_length=5000)


class InterviewOutcomeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    outcome: InterviewOutcome
