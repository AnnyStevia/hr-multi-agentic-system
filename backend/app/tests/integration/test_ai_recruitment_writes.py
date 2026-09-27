"""Integration: confirmation-gated recruitment writes (mocked LLM)."""

from unittest.mock import MagicMock

from app.ai.agents.recruitment import RecruitmentAgent, RecruitmentAgentRequest
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.modules.employees.dependencies import get_employee_service
from app.modules.employees.repository import DepartmentRepository
from app.modules.identity.models import User
from app.modules.interviews.meeting_service import InterviewMeetingService
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.models import Application, ApplicationStatus
from app.modules.recruitment.repository import ApplicationRepository, JobRepository
from app.modules.recruitment.service import JobService
from app.shared.meetings.fake import FakeMeetingProvider
from app.shared.storage import get_storage_service
from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_application_review import _submit_application


def _hr_write_context(user_id: int) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read", "recruitment:write"}),
        employee_id=None,
        candidate_id=None,
    )


def _build_agent(db_session, provider) -> RecruitmentAgent:
    storage = get_storage_service()
    notif = NotificationService(NotificationRepository(db_session))
    return RecruitmentAgent(
        llm_provider=provider,
        job_service=JobService(JobRepository(db_session), DepartmentRepository(db_session)),
        application_service=ApplicationService(db_session, storage, notif),
        interview_service=InterviewService(
            InterviewRepository(db_session),
            ApplicationRepository(db_session),
            notif,
        ),
        meeting_service=InterviewMeetingService(
            InterviewRepository(db_session),
            notifications=notif,
            provider=FakeMeetingProvider(),
        ),
        employee_service=get_employee_service(db_session),
        get_user=lambda uid: db_session.query(User).filter(User.id == uid).first(),
        db=db_session,
    )


def test_shortlist_ask_returns_pending_and_confirm_mutates(client, db_session):
    application, _job, _cand_headers, _storage = _submit_application(
        client, db_session, email="write.conf@test.com"
    )
    row = db_session.query(Application).filter(Application.id == application["id"]).one()
    row.status = ApplicationStatus.SCREENING
    db_session.commit()

    create_user_with_role(
        db_session,
        email="hr.write.conf@test.com",
        password="hrpass123",
        role_name="hr",
    )
    hr_user = db_session.query(User).filter(User.email == "hr.write.conf@test.com").one()

    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="shortlist_application",
                    arguments={"application_id": application["id"]},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Please confirm shortlisting in the UI.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = _build_agent(db_session, provider)
    answer = agent.ask(
        RecruitmentAgentRequest(
            question=f"Shortlist application {application['id']}",
            context=_hr_write_context(hr_user.id),
        )
    )
    assert answer.pending_confirmation is not None
    db_session.refresh(row)
    assert row.status == ApplicationStatus.SCREENING

    confirmed = agent.confirm(
        token=answer.pending_confirmation.token,
        context=_hr_write_context(hr_user.id),
    )
    assert "shortlist_application" in confirmed.tool_names_called
    db_session.refresh(row)
    assert row.status == ApplicationStatus.SHORTLISTED


def test_candidate_cannot_call_confirm_endpoint(client, db_session):
    create_user_with_role(
        db_session,
        email="cand.write.conf@test.com",
        password="pass12345",
        role_name="candidate",
    )
    headers = auth_header(client, email="cand.write.conf@test.com", password="pass12345")
    response = client.post(
        "/api/v1/ai/recruitment/confirm",
        json={"confirmation_token": "not-a-real-token-value-xx"},
        headers=headers,
    )
    assert response.status_code == 403
