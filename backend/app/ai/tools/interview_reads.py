"""AI tools that wrap InterviewService for HR recruitment agent (read-only)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.interviews.service import (
    InterviewService,
    build_interview_detail,
    build_interview_summary,
)
from app.shared.exceptions import AppException

_READ_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset({"recruitment:read"}),
    operates_on_current_user=False,
)


def _call_service(fn, *, error_message: str):
    try:
        return fn()
    except AppException as exc:
        raise ToolExecutionError(exc.message) from exc
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(error_message) from exc


class InterviewerBrief(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    name: str
    is_primary: bool = False


class SlotBrief(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    starts_at: datetime
    ends_at: datetime
    is_selected: bool = False
    is_available: bool = True


class InterviewBrief(BaseModel):
    """Compact interview payload suitable for LLM consumption."""

    model_config = {"extra": "forbid"}

    interview_id: int
    application_id: int
    status: str
    status_label: str
    candidate_name: str
    job_title: str
    primary_interviewer: InterviewerBrief | None = None
    panel_interviewers: list[InterviewerBrief] = Field(default_factory=list)
    slot_count: int = 0
    selected_slot: SlotBrief | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    meeting_available: bool = False
    meeting_url: str | None = None
    has_evaluation: bool = False
    outcome: str | None = None
    outcome_label: str | None = None
    completed_at: datetime | None = None


def _to_brief_from_summary(summary) -> InterviewBrief:
    primary = None
    panel: list[InterviewerBrief] = []
    for row in summary.interviewers or []:
        brief = InterviewerBrief(
            employee_id=row.employee_id,
            name=row.full_name,
            is_primary=bool(row.is_primary),
        )
        if row.is_primary:
            primary = brief
        else:
            panel.append(brief)
    if primary is None and summary.interviewer_name:
        primary = InterviewerBrief(
            employee_id=0,
            name=summary.interviewer_name,
            is_primary=True,
        )

    selected = None
    scheduled_start = None
    scheduled_end = None
    if summary.selected_slot is not None:
        selected = SlotBrief(
            id=summary.selected_slot.id,
            starts_at=summary.selected_slot.starts_at,
            ends_at=summary.selected_slot.ends_at,
            is_selected=summary.selected_slot.is_selected,
            is_available=summary.selected_slot.is_available,
        )
        scheduled_start = summary.selected_slot.starts_at
        scheduled_end = summary.selected_slot.ends_at

    meeting_url = (summary.meeting_url or None) or None
    return InterviewBrief(
        interview_id=summary.id,
        application_id=summary.application_id,
        status=summary.status,
        status_label=summary.status_label,
        candidate_name=summary.candidate_name,
        job_title=summary.job_title,
        primary_interviewer=primary,
        panel_interviewers=panel,
        slot_count=summary.slot_count,
        selected_slot=selected,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        meeting_available=bool(meeting_url),
        meeting_url=meeting_url,
        has_evaluation=summary.evaluation is not None,
        outcome=summary.outcome,
        outcome_label=summary.outcome_label,
        completed_at=summary.completed_at,
    )


def _to_brief_from_detail(detail) -> InterviewBrief:
    brief = _to_brief_from_summary(detail)
    # Detail may expose more slots; keep selected/scheduled from summary mapping.
    return brief


# --- get_interview ---


class GetInterviewInput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int = Field(ge=1)


class GetInterviewOutput(BaseModel):
    model_config = {"extra": "forbid"}

    interview: InterviewBrief
    proposed_slots: list[SlotBrief] = Field(default_factory=list)


class GetInterviewTool(BaseTool):
    name = "get_interview"
    description = (
        "Return one interview by interview_id for HR: status, status_label, "
        "primary/panel interviewers, slots, selected time, meeting link if any, "
        "and whether evaluation/outcome exist. Read-only."
    )
    metadata = _READ_META
    input_model = GetInterviewInput
    output_model = GetInterviewOutput

    def __init__(self, interview_service: InterviewService):
        self._interviews = interview_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetInterviewInput)
        interview = _call_service(
            lambda: self._interviews.get_for_hr(args.interview_id),
            error_message="Failed to retrieve interview",
        )
        detail = build_interview_detail(interview, include_evaluation=True)
        proposed = [
            SlotBrief(
                id=slot.id,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                is_selected=slot.is_selected,
                is_available=slot.is_available,
            )
            for slot in detail.slots
        ]
        return GetInterviewOutput(
            interview=_to_brief_from_detail(detail),
            proposed_slots=proposed,
        )


# --- list_interviews ---


class ListInterviewsInput(BaseModel):
    model_config = {"extra": "forbid"}

    status: str | None = Field(
        default=None,
        description="proposed | scheduled | completed | cancelled",
    )
    application_id: int | None = Field(default=None, ge=1)
    job_id: int | None = Field(default=None, ge=1)
    primary_employee_id: int | None = Field(default=None, ge=1)
    awaiting: Literal["primary_slots", "candidate_selection"] | None = Field(
        default=None,
        description=(
            "primary_slots = proposed with no slots yet; "
            "candidate_selection = proposed with slots awaiting candidate"
        ),
    )
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ListInterviewsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    count: int
    interviews: list[InterviewBrief]


class ListInterviewsTool(BaseTool):
    name = "list_interviews"
    description = (
        "List interviews for HR with optional filters: status, application_id, "
        "job_id, primary_employee_id, awaiting (primary_slots|candidate_selection). "
        "Bounded by limit/offset. Read-only."
    )
    metadata = _READ_META
    input_model = ListInterviewsInput
    output_model = ListInterviewsOutput

    def __init__(self, interview_service: InterviewService):
        self._interviews = interview_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListInterviewsInput)
        rows = _call_service(
            lambda: self._interviews.list_for_hr(
                status=args.status,
                application_id=args.application_id,
                job_id=args.job_id,
                primary_employee_id=args.primary_employee_id,
                awaiting=args.awaiting,
                limit=args.limit,
                offset=args.offset,
            ),
            error_message="Failed to list interviews",
        )
        briefs = [
            _to_brief_from_summary(build_interview_summary(row, include_evaluation=True))
            for row in rows
        ]
        return ListInterviewsOutput(count=len(briefs), interviews=briefs)


# --- get_interview_feedback ---


class GetInterviewFeedbackInput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int = Field(ge=1)


class GetInterviewFeedbackOutput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int
    available: bool
    message: str | None = None
    candidate_name: str | None = None
    job_title: str | None = None
    primary_interviewer_name: str | None = None
    tech_knowledge: int | None = None
    communication: int | None = None
    problem_solving: int | None = None
    relevant_experience: int | None = None
    strengths: str | None = None
    weaknesses: str | None = None
    additional_comments: str | None = None
    recommendation: str | None = None
    recommendation_label: str | None = None
    completed_at: datetime | None = None
    note: str | None = Field(
        default=None,
        description="Clarifies that recommendation is not an HR hiring decision",
    )


class GetInterviewFeedbackTool(BaseTool):
    name = "get_interview_feedback"
    description = (
        "Return structured interviewer feedback for an interview_id "
        "(ratings, strengths/weaknesses, recommendation). "
        "Recommendation is interviewer advice only, not an HR hire/reject decision. "
        "Read-only."
    )
    metadata = _READ_META
    input_model = GetInterviewFeedbackInput
    output_model = GetInterviewFeedbackOutput

    def __init__(self, interview_service: InterviewService):
        self._interviews = interview_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetInterviewFeedbackInput)
        interview = _call_service(
            lambda: self._interviews.get_for_hr(args.interview_id),
            error_message="Failed to retrieve interview feedback",
        )
        detail = build_interview_detail(interview, include_evaluation=True)
        evaluation = detail.evaluation
        if evaluation is None:
            return GetInterviewFeedbackOutput(
                interview_id=detail.id,
                available=False,
                message="No interviewer feedback is available for this interview yet.",
                candidate_name=detail.candidate_name,
                job_title=detail.job_title,
                primary_interviewer_name=detail.interviewer_name,
                completed_at=detail.completed_at,
            )
        return GetInterviewFeedbackOutput(
            interview_id=detail.id,
            available=True,
            candidate_name=detail.candidate_name,
            job_title=detail.job_title,
            primary_interviewer_name=detail.interviewer_name,
            tech_knowledge=evaluation.tech_knowledge,
            communication=evaluation.communication,
            problem_solving=evaluation.problem_solving,
            relevant_experience=evaluation.relevant_experience,
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            additional_comments=evaluation.additional_comments,
            recommendation=evaluation.recommendation,
            recommendation_label=evaluation.recommendation_label,
            completed_at=detail.completed_at,
            note=(
                "recommendation is the primary interviewer's advice only; "
                "it is not an HR hiring decision (see interview outcome separately)."
            ),
        )


# --- get_candidate_interviews ---


class GetCandidateInterviewsInput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int = Field(ge=1)


class GetCandidateInterviewsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int
    count: int
    interviews: list[InterviewBrief]


class GetCandidateInterviewsTool(BaseTool):
    name = "get_candidate_interviews"
    description = (
        "Return all interview rounds for an application_id (newest first). "
        "Preserves distinct interview_ids for multiple rounds. Read-only."
    )
    metadata = _READ_META
    input_model = GetCandidateInterviewsInput
    output_model = GetCandidateInterviewsOutput

    def __init__(self, interview_service: InterviewService):
        self._interviews = interview_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetCandidateInterviewsInput)
        rows = _call_service(
            lambda: self._interviews.list_for_application(args.application_id),
            error_message="Failed to list candidate interviews",
        )
        briefs = [
            _to_brief_from_summary(build_interview_summary(row, include_evaluation=True))
            for row in rows
        ]
        return GetCandidateInterviewsOutput(
            application_id=args.application_id,
            count=len(briefs),
            interviews=briefs,
        )


# --- get_upcoming_interviews ---


class GetUpcomingInterviewsInput(BaseModel):
    model_config = {"extra": "forbid"}

    days_ahead: int = Field(default=7, ge=1, le=14)
    limit: int = Field(default=20, ge=1, le=50)


class GetUpcomingInterviewsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    days_ahead: int
    count: int
    interviews: list[InterviewBrief]


class GetUpcomingInterviewsTool(BaseTool):
    name = "get_upcoming_interviews"
    description = (
        "Return scheduled upcoming interviews within days_ahead (1–14, default 7). "
        "Ordered by selected slot start time. Read-only."
    )
    metadata = _READ_META
    input_model = GetUpcomingInterviewsInput
    output_model = GetUpcomingInterviewsOutput

    def __init__(self, interview_service: InterviewService):
        self._interviews = interview_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetUpcomingInterviewsInput)
        rows = _call_service(
            lambda: self._interviews.list_upcoming_scheduled(
                days_ahead=args.days_ahead,
                limit=args.limit,
            ),
            error_message="Failed to list upcoming interviews",
        )
        briefs = [
            _to_brief_from_summary(build_interview_summary(row, include_evaluation=True))
            for row in rows
        ]
        return GetUpcomingInterviewsOutput(
            days_ahead=args.days_ahead,
            count=len(briefs),
            interviews=briefs,
        )
