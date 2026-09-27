"""Unit tests for confirmation tokens and gated interview write tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.confirmation import (
    ConfirmationError,
    create_confirmation_token,
    verify_confirmation_token,
)
from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    CreateInterviewInvitationTool,
    FindEmployeesTool,
    RetryInterviewMeetingTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolRegistry,
)
from app.modules.interviews.models import InterviewStatus
from app.modules.interviews.schemas import InterviewCreateRequest


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
