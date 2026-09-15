from datetime import datetime

from pydantic import BaseModel, Field


class InterviewSlotInput(BaseModel):
    model_config = {"extra": "forbid"}

    starts_at: datetime
    ends_at: datetime


class InterviewCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1, max_length=5000)
    slots: list[InterviewSlotInput] = Field(min_length=3, max_length=3)


class InterviewSlotResponse(BaseModel):
    id: int
    starts_at: datetime
    ends_at: datetime
    is_selected: bool
    is_available: bool


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
    selected_slot: InterviewSlotResponse | None = None


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
    slots: list[InterviewSlotResponse]
    selected_slot: InterviewSlotResponse | None = None


class InterviewConfirmRequest(BaseModel):
    model_config = {"extra": "forbid"}

    slot_id: int
