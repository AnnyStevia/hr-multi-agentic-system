"""Unit tests for confirmation tokens and gated interview write tools."""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.ai.agents.recruitment.agent import RecruitmentAgent, _format_confirm_answer
from app.ai.agents.recruitment.prompts import RECRUITMENT_AGENT_SYSTEM_PROMPT
from app.ai.agents.recruitment.schemas import RecruitmentAgentRequest
from app.ai.audit.models import AiToolActionAudit
from app.ai.confirmation import (
    ConfirmationError,
    create_confirmation_token,
    verify_confirmation_token,
)
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.ai.tools import (
    CreateInterviewInvitationTool,
    FindEmployeesTool,
    RecordInterviewOutcomeTool,
    RetryInterviewMeetingTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolRegistry,
)
from app.modules.interviews.models import InterviewOutcome, InterviewStatus
from app.modules.interviews.schemas import InterviewCreateRequest
from app.modules.recruitment.models import ApplicationStatus


def _hr_write(**overrides) -> AIExecutionContext:
    data = dict(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read", "recruitment:write"}),
        employee_id=10,
        candidate_id=None,
    )
    data.update(overrides)
    return AIExecutionContext(**data)


def test_confirmation_token_roundtrip_and_expiry_user_bind():
    token, payload = create_confirmation_token(
        user_id=7,
        tool_name="shortlist_application",
        arguments={"application_id": 3},
        summary="Shortlist app 3",
        ttl_seconds=120,
    )
    verified = verify_confirmation_token(token, user_id=7)
    assert verified.tool_name == "shortlist_application"
    assert verified.arguments == {"application_id": 3}
    with pytest.raises(ConfirmationError):
        verify_confirmation_token(token, user_id=8)
    with pytest.raises(ConfirmationError):
        verify_confirmation_token(token + "x", user_id=7)


def test_confirmation_token_expires():
    token, _payload = create_confirmation_token(
        user_id=1,
        tool_name="shortlist_application",
        arguments={"application_id": 1},
        summary="x",
        ttl_seconds=60,
    )
    with patch("app.ai.confirmation.tokens.time.time", return_value=time.time() + 10_000):
        with pytest.raises(ConfirmationError, match="expired"):
            verify_confirmation_token(token, user_id=1)


def test_confirmation_token_body_tamper_fails():
    token, _payload = create_confirmation_token(
        user_id=1,
        tool_name="shortlist_application",
        arguments={"application_id": 1},
        summary="x",
        ttl_seconds=120,
    )
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    body, sig = raw.rsplit(b".", 1)
    payload = json.loads(body)
    payload["arguments"] = {"application_id": 999}
    tampered_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad = base64.urlsafe_b64encode(tampered_body + b"." + sig).decode("ascii").rstrip("=")
    with pytest.raises(ConfirmationError):
        verify_confirmation_token(bad, user_id=1)


def test_format_confirm_answer_omits_raw_dump():
    text = _format_confirm_answer(
        "shortlist_application",
        "Proposed shortlist",
        {"application_id": 3, "new_status": "shortlisted", "secret_token": "leak"},
    )
    assert "Result: {" not in text
    assert "application_id: 3" in text
    assert "secret_token" not in text


def test_prompt_forbids_unguarded_writes_and_auto_hire():
    prompt = RECRUITMENT_AGENT_SYSTEM_PROMPT.lower()
    assert "confirmation" in prompt
    assert "never invent" in prompt
    assert "recommendation" in prompt
    assert "fit" in prompt


def test_create_invitation_pending_then_execute():
    interview_service = MagicMock()
    user = MagicMock()
    interview = MagicMock()
    interview.id = 44
    interview.application_id = 9
    interview.status = InterviewStatus.PROPOSED
    interview.message = None
    interview.meeting_url = None
    interview.slots = []
    interview.selected_slot = None
    interview.completed_at = None
    interview.outcome = None
    interview.feedback = None
    interview.recommendation = None
    interview.tech_knowledge = None
    interview.communication = None
    interview.problem_solving = None
    interview.relevant_experience = None
    interview.strengths = None
    interview.weaknesses = None
    interview.additional_comments = None
    interview.created_at = MagicMock()
    interview.updated_at = MagicMock()
    interview.application.candidate.user.full_name = "Sarah"
    interview.application.job.title = "Engineer"
    primary = MagicMock(id=2, full_name="John", position="Lead")
    assignment = MagicMock(employee_id=2, is_primary=True, employee=primary)
    interview.panel_assignments = [assignment]
    interview.interviewer = primary
    interview.interviewer_employee_id = 2
    interview_service.create_invitation.return_value = interview

    registry = ToolRegistry()
    registry.register(
        CreateInterviewInvitationTool(interview_service, get_user=lambda _id: user)
    )
    pending = ToolExecutor(registry).execute(
        _hr_write(),
        "create_interview_invitation",
        {
            "application_id": 9,
            "primary_employee_id": 2,
            "additional_employee_ids": [],
        },
    )
    assert pending.confirmation_token
    interview_service.create_invitation.assert_not_called()

    executed = ToolExecutor(registry).execute(
        _hr_write(),
        "create_interview_invitation",
        {
            "application_id": 9,
            "primary_employee_id": 2,
            "additional_employee_ids": [],
        },
        execute_writes=True,
    )
    assert executed.data["interview_id"] == 44
    interview_service.create_invitation.assert_called_once()
    call_kwargs = interview_service.create_invitation.call_args
    assert call_kwargs.args[0] == 9
    assert isinstance(call_kwargs.args[1], InterviewCreateRequest)
    assert call_kwargs.kwargs["created_by"] is user


def test_retry_meeting_pending_then_execute():
    meeting_service = MagicMock()
    interview = MagicMock()
    interview.id = 5
    interview.status = InterviewStatus.SCHEDULED
    interview.meeting_url = "https://meet.google.com/abc"
    meeting_service.ensure_meeting.return_value = interview
    registry = ToolRegistry()
    registry.register(RetryInterviewMeetingTool(meeting_service))
    pending = ToolExecutor(registry).execute(
        _hr_write(), "retry_interview_meeting", {"interview_id": 5}
    )
    assert pending.confirmation_token
    meeting_service.ensure_meeting.assert_not_called()
    done = ToolExecutor(registry).execute(
        _hr_write(),
        "retry_interview_meeting",
        {"interview_id": 5},
        execute_writes=True,
    )
    assert done.data["meeting_available"] is True
    meeting_service.ensure_meeting.assert_called_once_with(5)


def test_record_outcome_pending_then_execute():
    interview_service = MagicMock()
    interview = MagicMock()
    interview.id = 8
    interview.application_id = 12
    interview.status = InterviewStatus.COMPLETED
    interview.outcome = InterviewOutcome.REJECTED
    interview.message = None
    interview.meeting_url = None
    interview.slots = []
    interview.selected_slot = None
    interview.completed_at = MagicMock()
    interview.feedback = "ok"
    interview.recommendation = None
    interview.tech_knowledge = 3
    interview.communication = 3
    interview.problem_solving = 3
    interview.relevant_experience = 3
    interview.strengths = None
    interview.weaknesses = None
    interview.additional_comments = None
    interview.created_at = MagicMock()
    interview.updated_at = MagicMock()
    interview.application.candidate.user.full_name = "Sam"
    interview.application.job.title = "Dev"
    interview.panel_assignments = []
    interview.interviewer = MagicMock(id=2, full_name="Pat", position="Lead")
    interview.interviewer_employee_id = 2
    interview_service.record_outcome.return_value = interview
    interview_service.resolve_hired_employee_id.return_value = None

    registry = ToolRegistry()
    registry.register(RecordInterviewOutcomeTool(interview_service))
    pending = ToolExecutor(registry).execute(
        _hr_write(),
        "record_interview_outcome",
        {"interview_id": 8, "outcome": "rejected"},
    )
    assert pending.confirmation_token
    interview_service.record_outcome.assert_not_called()
    done = ToolExecutor(registry).execute(
        _hr_write(),
        "record_interview_outcome",
        {"interview_id": 8, "outcome": "rejected"},
        execute_writes=True,
    )
    assert done.data["outcome"] == "rejected"
    interview_service.record_outcome.assert_called_once()


def test_find_employees_multiple_matches_message():
    service = MagicMock()
    e1 = MagicMock(
        id=1,
        full_name="John A",
        email="a@x.com",
        position="Eng",
        employment_status=MagicMock(value="active"),
    )
    e1.department = MagicMock()
    e1.department.name = "Eng"
    e2 = MagicMock(
        id=2,
        full_name="John B",
        email="b@x.com",
        position="Eng",
        employment_status=MagicMock(value="active"),
    )
    e2.department = MagicMock()
    e2.department.name = "Eng"
    service.list_employees.return_value = ([e1, e2], 2)
    registry = ToolRegistry()
    registry.register(FindEmployeesTool(service))
    out = ToolExecutor(registry).execute(
        _hr_write(permission_names=frozenset({"recruitment:read"})),
        "find_employees",
        {"q": "John"},
    )
    assert out.data["count"] == 2
    assert "Multiple" in (out.data["message"] or "")


def test_write_tools_reject_candidate():
    registry = ToolRegistry()
    registry.register(RetryInterviewMeetingTool(MagicMock()))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            AIExecutionContext(
                user_id=9,
                role_names=frozenset({"candidate"}),
                permission_names=frozenset(),
                employee_id=None,
                candidate_id=3,
            ),
            "retry_interview_meeting",
            {"interview_id": 1},
        )


def test_agent_confirm_audits_proposed_confirmed_executed(db_session):
    app_service = MagicMock()
    current = MagicMock()
    current.id = 42
    current.status = ApplicationStatus.SCREENING
    current.candidate_id = 5
    current.candidate.user.full_name = "Jane"
    current.job_id = 3
    current.job.title = "Backend"
    updated = MagicMock()
    updated.id = 42
    updated.status = ApplicationStatus.SHORTLISTED
    updated.rejection_reason = None
    app_service.get_for_hr.return_value = current
    app_service.update_status.return_value = updated

    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="shortlist_application",
                    arguments={"application_id": 42},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Please confirm shortlisting.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = RecruitmentAgent(
        llm_provider=provider,
        job_service=MagicMock(),
        application_service=app_service,
        interview_service=MagicMock(),
        meeting_service=MagicMock(),
        employee_service=MagicMock(),
        get_user=lambda _uid: MagicMock(),
        db=db_session,
    )
    answer = agent.ask(
        RecruitmentAgentRequest(
            question="Shortlist application 42",
            context=_hr_write(),
        )
    )
    assert answer.pending_confirmation is not None
    proposed = (
        db_session.query(AiToolActionAudit)
        .filter(AiToolActionAudit.phase == "proposed")
        .all()
    )
    assert any(r.tool_name == "shortlist_application" for r in proposed)

    confirmed = agent.confirm(
        token=answer.pending_confirmation.token,
        context=_hr_write(),
    )
    assert "shortlist_application" in confirmed.tool_names_called
    assert "Result: {" not in confirmed.answer
    phases = {
        r.phase
        for r in db_session.query(AiToolActionAudit)
        .filter(AiToolActionAudit.tool_name == "shortlist_application")
        .all()
    }
    assert "proposed" in phases
    assert "confirmed" in phases
    assert "executed" in phases
    for row in db_session.query(AiToolActionAudit).all():
        assert row.arguments_digest is None or len(row.arguments_digest) == 64
