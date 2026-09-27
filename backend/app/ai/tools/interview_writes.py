"""AI write tools wrapping InterviewService / InterviewMeetingService (confirmation-gated)."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.identity.models import User
from app.modules.interviews.meeting_service import InterviewMeetingService
from app.modules.interviews.models import InterviewOutcome
from app.modules.interviews.schemas import InterviewCreateRequest
from app.modules.interviews.service import InterviewService, build_interview_detail
from app.shared.exceptions import AppException

_WRITE_META = ToolMetadata(
    operation="write",
    required_permissions=frozenset({"recruitment:write"}),
    operates_on_current_user=False,
    may_require_confirmation=True,
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


# --- create_interview_invitation ---


class CreateInterviewInvitationInput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int = Field(ge=1)
    primary_employee_id: int = Field(ge=1)
    additional_employee_ids: list[int] = Field(default_factory=list, max_length=19)
    message: str | None = Field(default=None, max_length=5000)


class CreateInterviewInvitationOutput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int
    application_id: int
    status: str
    status_label: str | None = None
    candidate_name: str
    job_title: str
    primary_employee_id: int
    primary_name: str | None = None
    panel_employee_ids: list[int] = Field(default_factory=list)
    message: str | None = None


class CreateInterviewInvitationTool(BaseTool):
    name = "create_interview_invitation"
    description = (
        "Create an interview invitation for a shortlisted application: assign exactly one "
        "primary interviewer and optional panel members. Requires confirmation. "
        "Does not propose slots or select a candidate slot. Write action."
    )
    metadata = _WRITE_META
    input_model = CreateInterviewInvitationInput
    output_model = CreateInterviewInvitationOutput

    def __init__(
        self,
        interview_service: InterviewService,
        get_user: Callable[[int], User | None],
    ):
        self._interviews = interview_service
        self._get_user = get_user

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, CreateInterviewInvitationInput)
        user = self._get_user(context.user_id)
        if user is None:
            raise ToolExecutionError("Authenticated user not found")
        payload = InterviewCreateRequest(
            primary_employee_id=args.primary_employee_id,
            additional_employee_ids=list(args.additional_employee_ids or []),
            message=args.message,
        )
        interview = _call_service(
            lambda: self._interviews.create_invitation(
                args.application_id, payload, created_by=user
            ),
            error_message="Failed to create interview invitation",
        )
        detail = build_interview_detail(interview, include_evaluation=False)
        primary = next((i for i in detail.interviewers if i.is_primary), None)
        panel_ids = [i.employee_id for i in detail.interviewers if not i.is_primary]
        return CreateInterviewInvitationOutput(
            interview_id=detail.id,
            application_id=detail.application_id,
            status=detail.status,
            status_label=detail.status_label,
            candidate_name=detail.candidate_name,
            job_title=detail.job_title,
            primary_employee_id=args.primary_employee_id,
            primary_name=primary.full_name if primary else detail.interviewer_name,
            panel_employee_ids=panel_ids,
            message=detail.message,
        )


# --- retry_interview_meeting ---


class RetryInterviewMeetingInput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int = Field(ge=1)


class RetryInterviewMeetingOutput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int
    status: str
    meeting_available: bool
    meeting_url: str | None = None
    message: str


class RetryInterviewMeetingTool(BaseTool):
    name = "retry_interview_meeting"
    description = (
        "Retry Google Meet provisioning for a scheduled interview via the existing "
        "meeting service (idempotent). Requires confirmation. Write action."
    )
    metadata = _WRITE_META
    input_model = RetryInterviewMeetingInput
    output_model = RetryInterviewMeetingOutput

    def __init__(self, meeting_service: InterviewMeetingService):
        self._meetings = meeting_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, RetryInterviewMeetingInput)
        interview = _call_service(
            lambda: self._meetings.ensure_meeting(args.interview_id),
            error_message="Failed to provision interview meeting",
        )
        url = (interview.meeting_url or "").strip() or None
        return RetryInterviewMeetingOutput(
            interview_id=interview.id,
            status=interview.status.value
            if hasattr(interview.status, "value")
            else str(interview.status),
            meeting_available=bool(url),
            meeting_url=url,
            message=(
                "Meeting link is available."
                if url
                else "Meeting link is still unavailable after retry."
            ),
        )


# --- record_interview_outcome ---


class RecordInterviewOutcomeInput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int = Field(ge=1)
    outcome: str = Field(
        description="rejected | another_interview | hired — explicit HR decision only"
    )


class RecordInterviewOutcomeOutput(BaseModel):
    model_config = {"extra": "forbid"}

    interview_id: int
    application_id: int
    outcome: str
    outcome_label: str | None = None
    candidate_name: str
    job_title: str
    hired_employee_id: int | None = None


class RecordInterviewOutcomeTool(BaseTool):
    name = "record_interview_outcome"
    description = (
        "Record the HR interview outcome (rejected, another_interview, or hired) "
        "for a completed interview. Use only on an explicit HR instruction. "
        "Never infer from interviewer recommendation or fit score. Requires confirmation."
    )
    metadata = _WRITE_META
    input_model = RecordInterviewOutcomeInput
    output_model = RecordInterviewOutcomeOutput

    def __init__(self, interview_service: InterviewService):
        self._interviews = interview_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, RecordInterviewOutcomeInput)
        try:
            outcome = InterviewOutcome(str(args.outcome).strip().lower())
        except ValueError as exc:
            raise ToolExecutionError(
                "outcome must be rejected, another_interview, or hired"
            ) from exc
        interview = _call_service(
            lambda: self._interviews.record_outcome(args.interview_id, outcome),
            error_message="Failed to record interview outcome",
        )
        hired_id = self._interviews.resolve_hired_employee_id(interview)
        detail = build_interview_detail(
            interview, hired_employee_id=hired_id, include_evaluation=True
        )
        return RecordInterviewOutcomeOutput(
            interview_id=detail.id,
            application_id=detail.application_id,
            outcome=detail.outcome or outcome.value,
            outcome_label=detail.outcome_label,
            candidate_name=detail.candidate_name,
            job_title=detail.job_title,
            hired_employee_id=detail.hired_employee_id,
        )
