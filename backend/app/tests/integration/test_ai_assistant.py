"""Integration: unified POST /ai/assistant/ask gateway."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.agents.leave.schemas import LeaveAgentAnswer, PendingConfirmationInfo
from app.ai.agents.onboarding.schemas import (
    OnboardingAgentAnswer,
    PendingConfirmationInfo as OnboardingPending,
)
from app.ai.agents.recruitment.schemas import (
    PendingConfirmationInfo as RecPending,
)
from app.ai.agents.recruitment.schemas import RecruitmentAgentAnswer
from app.ai.agents.training.schemas import (
    PendingConfirmationInfo as TrainingPending,
    TrainingAgentAnswer,
)
from app.ai.rag.generation.schemas import Citation, RAGAnswer
from app.api.v1 import (
    ai_knowledge,
    ai_leave,
    ai_onboarding,
    ai_recruitment,
    ai_training,
)
from app.tests.helpers import auth_header, create_user_with_role


def test_assistant_ask_requires_auth(client):
    response = client.post(
        "/api/v1/ai/assistant/ask",
        json={"message": "What is my leave balance?"},
    )
    assert response.status_code == 401


def test_unified_ask_routes_to_leave(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.asst.leave@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.asst.leave@test.com", password="pass12345"
    )
    mock_leave = MagicMock()
    mock_leave.ask.return_value = LeaveAgentAnswer(
        answer="You have 12 days left.",
        model="mock-leave",
        tool_names_called=["get_my_leave_balance"],
        usage=None,
        pending_confirmation=None,
    )
    mock_knowledge = MagicMock()
    mock_recruitment = MagicMock()
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: mock_knowledge
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_recruitment
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "What's my remaining annual leave?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["agent_id"] == "leave"
    assert body["answer"] == "You have 12 days left."
    assert body["tool_names_called"] == ["get_my_leave_balance"]
    assert body["citations"] == []
    assert body["pending_confirmation"] is None
    mock_leave.ask.assert_called_once()
    mock_knowledge.ask.assert_not_called()
    mock_recruitment.ask.assert_not_called()


def test_unified_ask_routes_to_knowledge_preserves_citations(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.asst.know@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.asst.know@test.com", password="pass12345"
    )
    mock_knowledge = MagicMock()
    mock_knowledge.ask.return_value = RAGAnswer(
        query="handbook leave",
        answer="Employees get 20 days [1]",
        citations=[
            Citation(
                citation_id=1,
                chunk_id=9,
                company_document_id=3,
                page_start=2,
                page_end=2,
                document_name="Employee Handbook",
                content_hash="b" * 64,
            )
        ],
        has_context=True,
        retrieval_count=1,
        selected_context_count=1,
        model="mock-knowledge",
    )
    mock_leave = MagicMock()
    mock_recruitment = MagicMock()
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: mock_knowledge
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_recruitment
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={
                "message": (
                    "According to the employee handbook, "
                    "how many days of annual leave do we get?"
                )
            },
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["agent_id"] == "knowledge"
    assert body["citations"][0]["citation_id"] == 1
    assert body["citations"][0]["document_name"] == "Employee Handbook"
    assert "content_hash" not in body["citations"][0]
    mock_knowledge.ask.assert_called_once()
    mock_leave.ask.assert_not_called()
    mock_recruitment.ask.assert_not_called()


def test_unified_ask_routes_to_recruitment_preserves_pending(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.asst.rec@test.com",
        password="hrpass123",
        role_name="hr",
    )
    headers = auth_header(
        client, email="hr.asst.rec@test.com", password="hrpass123"
    )
    mock_recruitment = MagicMock()
    mock_recruitment.ask.return_value = RecruitmentAgentAnswer(
        answer="Confirm reject?",
        model="mock-rec",
        tool_names_called=["reject_application"],
        usage=None,
        pending_confirmation=RecPending(
            token="tok-abc",
            tool_name="reject_application",
            summary="Reject application #12",
            expires_at=9999999999,
        ),
    )
    mock_leave = MagicMock()
    mock_knowledge = MagicMock()
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_recruitment
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: mock_knowledge
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "How many candidates are currently shortlisted?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["agent_id"] == "recruitment"
    assert body["pending_confirmation"]["token"] == "tok-abc"
    assert body["pending_confirmation"]["tool_name"] == "reject_application"
    mock_recruitment.ask.assert_called_once()
    mock_leave.ask.assert_not_called()
    mock_knowledge.ask.assert_not_called()


def test_unified_ask_leave_preserves_pending_confirmation(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.asst.pend@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.asst.pend@test.com", password="pass12345"
    )
    mock_leave = MagicMock()
    mock_leave.ask.return_value = LeaveAgentAnswer(
        answer="Please confirm cancel.",
        model="mock",
        tool_names_called=["cancel_my_leave_request"],
        pending_confirmation=PendingConfirmationInfo(
            token="leave-tok",
            tool_name="cancel_my_leave_request",
            summary="Cancel leave #5",
            expires_at=8888888888,
        ),
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: MagicMock()
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: MagicMock()
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "Cancel leave for my pending request"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_id"] == "leave"
    assert body["pending_confirmation"]["token"] == "leave-tok"


def test_clarification_response(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.asst.clarify@test.com",
        password="hrpass123",
        role_name="hr",
    )
    headers = auth_header(
        client, email="hr.asst.clarify@test.com", password="hrpass123"
    )
    mock_rec = MagicMock()
    mock_leave = MagicMock()
    mock_know = MagicMock()
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_rec
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: mock_know
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "Tell me about interviews."},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "clarification_required"
    assert body["agent_id"] is None
    mock_rec.ask.assert_not_called()
    mock_leave.ask.assert_not_called()
    mock_know.ask.assert_not_called()


def test_employee_recruitment_request_never_invokes_recruitment_agent(
    client, db_session
):
    create_user_with_role(
        db_session,
        email="emp.asst.norec@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.asst.norec@test.com", password="pass12345"
    )
    mock_recruitment = MagicMock()
    mock_leave = MagicMock()
    mock_knowledge = MagicMock()
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_recruitment
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: mock_knowledge
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "Reject this candidate."},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["agent_id"] is None
    mock_recruitment.ask.assert_not_called()
    mock_leave.ask.assert_not_called()
    mock_knowledge.ask.assert_not_called()


def test_manager_recruitment_request_never_invokes_recruitment_agent(
    client, db_session
):
    create_user_with_role(
        db_session,
        email="mgr.asst.norec@test.com",
        password="mgrpass123",
        role_name="manager",
    )
    headers = auth_header(
        client, email="mgr.asst.norec@test.com", password="mgrpass123"
    )
    mock_recruitment = MagicMock()
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_recruitment
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: MagicMock()
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: MagicMock()
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "Shortlist candidate John for the backend role"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unavailable"
    mock_recruitment.ask.assert_not_called()


def test_candidate_gets_unavailable_no_agents(client, db_session):
    create_user_with_role(
        db_session,
        email="cand.asst@test.com",
        password="pass12345",
        role_name="candidate",
    )
    headers = auth_header(
        client, email="cand.asst@test.com", password="pass12345"
    )
    mock_rec = MagicMock()
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_rec
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: MagicMock()
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: MagicMock()
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "What is my leave balance?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unavailable"
    mock_rec.ask.assert_not_called()


def test_unified_ask_routes_to_onboarding_preserves_pending(client, db_session):
    # HR has onboarding:read (no Employee row required for registry availability).
    create_user_with_role(
        db_session,
        email="hr.asst.onb@test.com",
        password="hrpass123",
        role_name="hr",
    )
    headers = auth_header(
        client, email="hr.asst.onb@test.com", password="hrpass123"
    )
    mock_onboarding = MagicMock()
    mock_onboarding.ask.return_value = OnboardingAgentAnswer(
        answer="Confirm acknowledge task?",
        model="mock-onb",
        tool_names_called=["acknowledge_onboarding_task"],
        usage=None,
        pending_confirmation=OnboardingPending(
            token="onb-tok",
            tool_name="acknowledge_onboarding_task",
            summary="Acknowledge task #7",
            expires_at=7777777777,
        ),
    )
    mock_leave = MagicMock()
    mock_knowledge = MagicMock()
    mock_recruitment = MagicMock()
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_onboarding
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: mock_knowledge
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_recruitment
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "What's my onboarding progress?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["agent_id"] == "onboarding"
    assert body["answer"] == "Confirm acknowledge task?"
    assert body["pending_confirmation"]["token"] == "onb-tok"
    assert body["pending_confirmation"]["tool_name"] == "acknowledge_onboarding_task"
    assert body["tool_names_called"] == ["acknowledge_onboarding_task"]
    mock_onboarding.ask.assert_called_once()
    mock_leave.ask.assert_not_called()
    mock_knowledge.ask.assert_not_called()
    mock_recruitment.ask.assert_not_called()


def test_unified_ask_routes_to_training_preserves_pending(client, db_session):
    # HR has training:read + staff role (no Employee row required for availability).
    create_user_with_role(
        db_session,
        email="hr.asst.train@test.com",
        password="hrpass123",
        role_name="hr",
    )
    headers = auth_header(
        client, email="hr.asst.train@test.com", password="hrpass123"
    )
    mock_training = MagicMock()
    mock_training.ask.return_value = TrainingAgentAnswer(
        answer="Confirm complete training assignment?",
        model="mock-train",
        tool_names_called=["complete_my_training_assignment"],
        usage=None,
        pending_confirmation=TrainingPending(
            token="train-tok",
            tool_name="complete_my_training_assignment",
            summary="Complete assignment 11",
            expires_at=8888888888,
        ),
    )
    mock_leave = MagicMock()
    mock_knowledge = MagicMock()
    mock_recruitment = MagicMock()
    mock_onboarding = MagicMock()
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_training
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: mock_knowledge
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: mock_recruitment
    )
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_onboarding
    )
    try:
        response = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "What trainings do I have?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["agent_id"] == "training"
    assert body["answer"] == "Confirm complete training assignment?"
    assert body["pending_confirmation"]["token"] == "train-tok"
    assert (
        body["pending_confirmation"]["tool_name"]
        == "complete_my_training_assignment"
    )
    assert body["tool_names_called"] == ["complete_my_training_assignment"]
    mock_training.ask.assert_called_once()
    mock_leave.ask.assert_not_called()
    mock_knowledge.ask.assert_not_called()
    mock_recruitment.ask.assert_not_called()
    mock_onboarding.ask.assert_not_called()


def test_existing_leave_endpoint_still_works(client, db_session):
    """Regression: per-agent endpoints remain."""
    create_user_with_role(
        db_session,
        email="emp.asst.legacy@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.asst.legacy@test.com", password="pass12345"
    )
    mock_leave = MagicMock()
    mock_leave.ask.return_value = LeaveAgentAnswer(
        answer="ok",
        model="mock",
        tool_names_called=[],
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    try:
        response = client.post(
            "/api/v1/ai/leave/ask",
            json={"question": "My leave balance?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
    assert response.status_code == 200, response.text
    assert "agent_id" not in response.json()
