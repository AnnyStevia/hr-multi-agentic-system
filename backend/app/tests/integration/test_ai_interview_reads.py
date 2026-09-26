"""Integration: interview read tools via InterviewService + DB (mocked LLM)."""

from unittest.mock import MagicMock, patch

from app.ai.agents.recruitment import RecruitmentAgent, RecruitmentAgentRequest
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.ai.tools import GetInterviewTool, GetUpcomingInterviewsTool, ToolExecutor, ToolRegistry
from app.modules.interviews.models import Interview, InterviewStatus
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.repository import ApplicationRepository
from app.shared.meetings.fake import FakeMeetingProvider
from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_application_review import _submit_application
from app.tests.integration.test_interview_invitations import _create_invitation


def _hr_ai_context(user_id: int) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read", "recruitment:write"}),
        employee_id=None,
        candidate_id=None,
    )


def _interview_service(db_session) -> InterviewService:
    notifications = NotificationService(NotificationRepository(db_session))
    return InterviewService(
        InterviewRepository(db_session),
        ApplicationRepository(db_session),
        notifications,
        application_service=None,
    )


def test_get_interview_tool_reads_meeting_url_from_db(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client, db_session, email="ai.iv.meet@test.com"
    )
    interview, headers, _primary = _create_invitation(
        client, db_session, application["id"]
    )
    slot_id = interview["slots"][0]["id"]
    assert (
        client.post(
            f"/api/v1/careers/interviews/{interview['id']}/confirm",
            json={"slot_id": slot_id},
            headers=candidate_headers,
        ).status_code
        == 200
    )
    with patch(
        "app.modules.interviews.dependencies.get_meeting_provider",
        return_value=FakeMeetingProvider(),
    ):
        ensured = client.post(
            f"/api/v1/interviews/{interview['id']}/meeting",
            headers=headers,
        )
    assert ensured.status_code == 200
    meeting_url = ensured.json()["meeting_url"]
    assert meeting_url

    service = _interview_service(db_session)
    registry = ToolRegistry()
    registry.register(GetInterviewTool(service))
    result = ToolExecutor(registry).execute(
        _hr_ai_context(1),
        "get_interview",
        {"interview_id": interview["id"]},
    )
    assert result.success is True
    assert result.data["interview"]["meeting_available"] is True
    assert result.data["interview"]["meeting_url"] == meeting_url
    assert result.data["interview"]["status"] == "scheduled"


def test_upcoming_tool_lists_scheduled_interview(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client, db_session, email="ai.iv.up@test.com"
    )
    interview, _headers, _primary = _create_invitation(
        client, db_session, application["id"]
    )
    slot_id = interview["slots"][0]["id"]
    assert (
        client.post(
            f"/api/v1/careers/interviews/{interview['id']}/confirm",
            json={"slot_id": slot_id},
            headers=candidate_headers,
        ).status_code
        == 200
    )
    row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    assert row.status == InterviewStatus.SCHEDULED

    service = _interview_service(db_session)
    registry = ToolRegistry()
    registry.register(GetUpcomingInterviewsTool(service))
    result = ToolExecutor(registry).execute(
        _hr_ai_context(1),
        "get_upcoming_interviews",
        {"days_ahead": 14, "limit": 20},
    )
    assert result.success is True
    ids = [item["interview_id"] for item in result.data["interviews"]]
    assert interview["id"] in ids


def test_agent_ask_uses_get_interview_with_seeded_data(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client, db_session, email="ai.iv.agent@test.com"
    )
    interview, _headers, _primary = _create_invitation(
        client, db_session, application["id"]
    )
    interview_id = interview["id"]

    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="get_interview",
                    arguments={"interview_id": interview_id},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content=f"Interview {interview_id} is waiting for the candidate.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = _interview_service(db_session)
    agent = RecruitmentAgent(
        llm_provider=provider,
        job_service=MagicMock(),
        application_service=MagicMock(),
        interview_service=service,
    )
    hr_user = create_user_with_role(
        db_session,
        email="hr.ai.iv@test.com",
        password="hrpass123",
        role_name="hr",
    )
    answer = agent.ask(
        RecruitmentAgentRequest(
            question=f"Who is interviewing for interview {interview_id}?",
            context=_hr_ai_context(hr_user.id),
        )
    )
    assert answer.tool_names_called == ["get_interview"]
    assert str(interview_id) in answer.answer


def test_candidate_still_forbidden_on_recruitment_ask(client, db_session):
    create_user_with_role(
        db_session,
        email="cand.ai.iv@test.com",
        password="pass12345",
        role_name="candidate",
    )
    headers = auth_header(client, email="cand.ai.iv@test.com", password="pass12345")
    response = client.post(
        "/api/v1/ai/recruitment/ask",
        json={"question": "What interviews are scheduled?"},
        headers=headers,
    )
    assert response.status_code == 403
