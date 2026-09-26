from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.interviews.models import InterviewerRecommendation, InterviewOutcome


class InterviewSlotInput(BaseModel):
    model_config = {"extra": "forbid"}

    starts_at: datetime
    ends_at: datetime


class InterviewCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    primary_employee_id: int = Field(ge=1)
    additional_employee_ids: list[int] = Field(default_factory=list, max_length=19)
    message: str | None = Field(default=None, max_length=5000)


class InterviewProposeSlotsRequest(BaseModel):
    model_config = {"extra": "forbid"}

    slots: list[InterviewSlotInput] = Field(min_length=1, max_length=10)


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
    is_primary: bool = False


class InterviewFeedbackView(BaseModel):
    tech_knowledge: int | None = None
    communication: int | None = None
    problem_solving: int | None = None
    relevant_experience: int | None = None
    strengths: str | None = None
    weaknesses: str | None = None
    additional_comments: str | None = None
    recommendation: str | None = None
    recommendation_label: str | None = None


class InterviewSummary(BaseModel):
    id: int
    application_id: int
    status: str
    status_label: str
    message: str | None
    created_at: datetime
    job_title: str
    candidate_name: str
    interviewer_name: str | None
    interviewers: list[InterviewerSummary] = Field(default_factory=list)
    selected_slot: InterviewSlotResponse | None = None
    slot_count: int = 0
    feedback: str | None = None
    evaluation: InterviewFeedbackView | None = None
    completed_at: datetime | None = None
    outcome: str | None = None
    outcome_label: str | None = None
    hired_employee_id: int | None = None
    meeting_url: str | None = None
    my_role: str | None = None
    can_propose_slots: bool = False
    can_complete: bool = False


class InterviewDetailResponse(BaseModel):
    id: int
    application_id: int
    status: str
    status_label: str | None = None
    message: str | None
    created_at: datetime
    updated_at: datetime
    job_title: str
    candidate_name: str
    interviewer_name: str | None
    interviewers: list[InterviewerSummary] = Field(default_factory=list)
    slots: list[InterviewSlotResponse]
    selected_slot: InterviewSlotResponse | None = None
    slot_count: int = 0
    feedback: str | None = None
    evaluation: InterviewFeedbackView | None = None
    completed_at: datetime | None = None
    outcome: str | None = None
    outcome_label: str | None = None
    hired_employee_id: int | None = None
    meeting_url: str | None = None
    my_role: str | None = None
    can_propose_slots: bool = False
    can_complete: bool = False


class InterviewConfirmRequest(BaseModel):
    model_config = {"extra": "forbid"}

    slot_id: int


class InterviewCompleteRequest(BaseModel):
    model_config = {"extra": "forbid"}

    tech_knowledge: int = Field(ge=1, le=5)
    communication: int = Field(ge=1, le=5)
    problem_solving: int = Field(ge=1, le=5)
    relevant_experience: int = Field(ge=1, le=5)
    strengths: str = Field(min_length=1, max_length=5000)
    weaknesses: str = Field(min_length=1, max_length=5000)
    additional_comments: str | None = Field(default=None, max_length=5000)
    recommendation: InterviewerRecommendation


class InterviewOutcomeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    outcome: InterviewOutcome
