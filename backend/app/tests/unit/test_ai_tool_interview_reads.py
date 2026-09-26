"""Unit tests for interview read AI tools (mocked InterviewService; no Gemini/Google)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    GetCandidateInterviewsTool,
    GetInterviewFeedbackTool,
    GetInterviewTool,
    GetUpcomingInterviewsTool,
    ListInterviewsTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolExecutionError,
    ToolRegistry,
)
from app.modules.interviews.models import (
    InterviewerRecommendation,
    InterviewOutcome,
    InterviewStatus,
)
from app.shared.exceptions import AppException


def _hr_context(**overrides) -> AIExecutionContext:
    data = dict(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )
    data.update(overrides)
    return AIExecutionContext(**data)


def _employee_context() -> AIExecutionContext:
    return _hr_context(
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
    )


def _candidate_context() -> AIExecutionContext:
    return _hr_context(
        role_names=frozenset({"candidate"}),
        permission_names=frozenset(),
        employee_id=None,
        candidate_id=5,
    )


def _slot(*, slot_id: int = 1, selected: bool = False, hours: int = 24):
    start = datetime.now(UTC) + timedelta(hours=hours)
    return SimpleNamespace(
        id=slot_id,
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
        is_selected=selected,
        is_available=not selected or True,
    )


def _interview(
    *,
    interview_id: int = 1,
    application_id: int = 10,
    status: InterviewStatus = InterviewStatus.SCHEDULED,
    meeting_url: str | None = "https://meet.google.com/abc-defg-hij",
    slots: list | None = None,
    selected_slot=None,
    with_evaluation: bool = False,
    outcome: InterviewOutcome | None = None,
    cancelled: bool = False,
):
    if cancelled:
        status = InterviewStatus.CANCELLED
    primary = SimpleNamespace(id=2, full_name="Pat Primary", position="Lead")
    panel = SimpleNamespace(id=3, full_name="Sam Panel", position="Eng")
    assignment_primary = SimpleNamespace(
        employee_id=2, is_primary=True, employee=primary
    )
    assignment_panel = SimpleNamespace(
        employee_id=3, is_primary=False, employee=panel
    )
    if slots is None:
        if status == InterviewStatus.PROPOSED:
            slots = []
        else:
            selected = selected_slot or _slot(slot_id=5, selected=True)
            slots = [selected]
            selected_slot = selected

    candidate_user = SimpleNamespace(full_name="Ada Lovelace", id=50)
    candidate = SimpleNamespace(user=candidate_user, user_id=50)
    job = SimpleNamespace(title="Backend Engineer", id=7)
    application = SimpleNamespace(
        id=application_id, candidate=candidate, job=job, job_id=7
    )

    inv = MagicMock()
    inv.id = interview_id
    inv.application_id = application_id
    inv.application = application
    inv.status = status
    inv.message = None
    inv.created_at = datetime(2026, 9, 1, tzinfo=UTC)
    inv.updated_at = datetime(2026, 9, 2, tzinfo=UTC)
    inv.slots = slots
    inv.selected_slot = selected_slot
    inv.selected_slot_id = selected_slot.id if selected_slot else None
    inv.interviewer = primary
    inv.interviewer_employee_id = primary.id
    inv.panel_assignments = [assignment_primary, assignment_panel]
    inv.meeting_url = meeting_url
    inv.meeting_external_id = "evt-1" if meeting_url else None
    inv.feedback = "Good" if with_evaluation else None
    inv.tech_knowledge = 4 if with_evaluation else None
    inv.communication = 5 if with_evaluation else None
    inv.problem_solving = 4 if with_evaluation else None
    inv.relevant_experience = 3 if with_evaluation else None
    inv.strengths = "API design" if with_evaluation else None
    inv.weaknesses = "System design depth" if with_evaluation else None
    inv.additional_comments = "Hire-track" if with_evaluation else None
    inv.recommendation = (
        InterviewerRecommendation.PROCEED if with_evaluation else None
    )
    inv.completed_at = datetime(2026, 9, 10, tzinfo=UTC) if with_evaluation else None
    inv.completed_by_employee_id = 2 if with_evaluation else None
    inv.outcome = outcome
    return inv


def _executor(service: MagicMock) -> ToolExecutor:
    registry = ToolRegistry()
    registry.register(GetInterviewTool(service))
    registry.register(ListInterviewsTool(service))
    registry.register(GetInterviewFeedbackTool(service))
    registry.register(GetCandidateInterviewsTool(service))
    registry.register(GetUpcomingInterviewsTool(service))
    return ToolExecutor(registry)


def test_get_interview_with_meeting_url():
    service = MagicMock()
    service.get_for_hr.return_value = _interview(meeting_url="https://meet.google.com/zz")
    out = _executor(service).execute(
        _hr_context(), "get_interview", {"interview_id": 1}
    )
    assert out.success is True
    assert out.data["interview"]["meeting_available"] is True
    assert out.data["interview"]["meeting_url"] == "https://meet.google.com/zz"
    assert out.data["interview"]["primary_interviewer"]["name"] == "Pat Primary"
    assert out.data["interview"]["primary_interviewer"]["is_primary"] is True
    assert len(out.data["interview"]["panel_interviewers"]) == 1


def test_get_interview_without_meeting_url():
    service = MagicMock()
    service.get_for_hr.return_value = _interview(meeting_url=None)
    out = _executor(service).execute(
        _hr_context(), "get_interview", {"interview_id": 1}
    )
    assert out.data["interview"]["meeting_available"] is False
    assert out.data["interview"]["meeting_url"] is None


def test_get_interview_missing():
    service = MagicMock()
    service.get_for_hr.side_effect = AppException("Interview not found", status_code=404)
    with pytest.raises(ToolExecutionError, match="not found"):
        _executor(service).execute(
            _hr_context(), "get_interview", {"interview_id": 999}
        )

def test_list_interviews_awaiting_primary_slots():
    service = MagicMock()
    service.list_for_hr.return_value = [
        _interview(status=InterviewStatus.PROPOSED, meeting_url=None, slots=[])
    ]
    out = _executor(service).execute(
        _hr_context(),
        "list_interviews",
        {"awaiting": "primary_slots"},
    )
    assert out.success is True
    assert out.data["count"] == 1
    assert "primary" in out.data["interviews"][0]["status_label"].lower()
    service.list_for_hr.assert_called_once()
    kwargs = service.list_for_hr.call_args.kwargs
    assert kwargs["awaiting"] == "primary_slots"


def test_list_interviews_awaiting_candidate_selection():
    service = MagicMock()
    slots = [_slot(slot_id=1), _slot(slot_id=2, hours=48)]
    service.list_for_hr.return_value = [
        _interview(
            status=InterviewStatus.PROPOSED,
            meeting_url=None,
            slots=slots,
            selected_slot=None,
        )
    ]
    out = _executor(service).execute(
        _hr_context(),
        "list_interviews",
        {"awaiting": "candidate_selection"},
    )
    assert out.data["count"] == 1
    assert "candidate" in out.data["interviews"][0]["status_label"].lower()


def test_get_interview_feedback_available():
    service = MagicMock()
    service.get_for_hr.return_value = _interview(
        status=InterviewStatus.COMPLETED,
        with_evaluation=True,
        meeting_url=None,
    )
    out = _executor(service).execute(
        _hr_context(), "get_interview_feedback", {"interview_id": 1}
    )
    assert out.data["available"] is True
    assert out.data["recommendation"] == "proceed"
    assert "not an hr hiring decision" in (out.data["note"] or "").lower()
    assert out.data["tech_knowledge"] == 4


def test_get_interview_feedback_missing():
    service = MagicMock()
    service.get_for_hr.return_value = _interview(
        status=InterviewStatus.SCHEDULED, with_evaluation=False
    )
    out = _executor(service).execute(
        _hr_context(), "get_interview_feedback", {"interview_id": 1}
    )
    assert out.data["available"] is False
    assert out.data["recommendation"] is None


def test_get_candidate_interviews_preserves_multiple_rounds():
    service = MagicMock()
    service.list_for_application.return_value = [
        _interview(interview_id=20, status=InterviewStatus.SCHEDULED),
        _interview(
            interview_id=10,
            status=InterviewStatus.COMPLETED,
            with_evaluation=True,
            meeting_url=None,
        ),
    ]
    out = _executor(service).execute(
        _hr_context(),
        "get_candidate_interviews",
        {"application_id": 10},
    )
    assert out.data["count"] == 2
    ids = [item["interview_id"] for item in out.data["interviews"]]
    assert ids == [20, 10]


def test_get_upcoming_interviews():
    service = MagicMock()
    service.list_upcoming_scheduled.return_value = [
        _interview(interview_id=5, status=InterviewStatus.SCHEDULED)
    ]
    out = _executor(service).execute(
        _hr_context(),
        "get_upcoming_interviews",
        {"days_ahead": 7, "limit": 10},
    )
    assert out.data["count"] == 1
    assert out.data["days_ahead"] == 7
    service.list_upcoming_scheduled.assert_called_once_with(days_ahead=7, limit=10)


def test_completed_and_cancelled_shapes():
    service = MagicMock()
    service.get_for_hr.side_effect = [
        _interview(
            interview_id=1,
            status=InterviewStatus.COMPLETED,
            with_evaluation=True,
            outcome=InterviewOutcome.HIRED,
            meeting_url=None,
        ),
        _interview(interview_id=2, cancelled=True, meeting_url=None, slots=[]),
    ]
    completed = _executor(service).execute(
        _hr_context(), "get_interview", {"interview_id": 1}
    )
    cancelled = _executor(service).execute(
        _hr_context(), "get_interview", {"interview_id": 2}
    )
    assert completed.data["interview"]["status"] == "completed"
    assert completed.data["interview"]["outcome"] == "hired"
    assert cancelled.data["interview"]["status"] == "cancelled"


def test_unauthorized_contexts_rejected():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(GetInterviewTool(service))
    executor = ToolExecutor(registry)
    for ctx in (_employee_context(), _candidate_context()):
        with pytest.raises(ToolAuthorizationError):
            executor.execute(ctx, "get_interview", {"interview_id": 1})
    service.get_for_hr.assert_not_called()


def test_output_schema_forbids_extra_fields():
    from app.ai.tools.interview_reads import InterviewBrief

    with pytest.raises(Exception):
        InterviewBrief.model_validate(
            {
                "interview_id": 1,
                "application_id": 1,
                "status": "scheduled",
                "status_label": "Scheduled",
                "candidate_name": "Ada",
                "job_title": "Eng",
                "secret_token": "nope",
            }
        )
