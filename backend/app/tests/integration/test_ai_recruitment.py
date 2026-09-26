"""API tests for Recruitment Agent ask endpoint (mocked agent; no Gemini)."""

from unittest.mock import MagicMock

from app.ai.agents.recruitment.schemas import RecruitmentAgentAnswer
from app.api.v1 import ai_recruitment
from app.tests.helpers import auth_header, create_user_with_role


def test_ask_requires_auth(client):
    response = client.post("/api/v1/ai/recruitment/ask", json={"question": "Hello"})
    assert response.status_code == 401


def test_candidate_cannot_ask_recruitment(client, db_session):
    create_user_with_role(
        db_session,
        email="cand.recruit.ai@test.com",
        password="pass12345",
        role_name="candidate",
    )
    headers = auth_header(client, email="cand.recruit.ai@test.com", password="pass12345")
    response = client.post(
        "/api/v1/ai/recruitment/ask",
        json={"question": "List applications"},
        headers=headers,
    )
    assert response.status_code == 403


def test_employee_cannot_ask_recruitment(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.recruit.ai@test.com",
        password="emppass123",
        role_name="employee",
    )
    headers = auth_header(client, email="emp.recruit.ai@test.com", password="emppass123")
    response = client.post(
        "/api/v1/ai/recruitment/ask",
        json={"question": "List applications"},
        headers=headers,
    )
    assert response.status_code == 403


def test_hr_ask_returns_answer(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.recruit.ai@test.com",
        password="hrpass123",
        role_name="hr",
        first_name="Amina",
        last_name="HR",
    )
    headers = auth_header(client, email="hr.recruit.ai@test.com", password="hrpass123")

    mock_agent = MagicMock()
    mock_agent.ask.return_value = RecruitmentAgentAnswer(
        answer="Application 3 is submitted.",
        model="mock",
        tool_names_called=["get_application"],
        usage=None,
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = lambda: mock_agent
    try:
        response = client.post(
            "/api/v1/ai/recruitment/ask",
            json={"question": "Status of application 3?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_recruitment.get_recruitment_agent, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "Application 3 is submitted."
    assert body["tool_names_called"] == ["get_application"]
    assert body["model"] == "mock"


def test_admin_ask_allowed(client, db_session):
    headers = auth_header(client)
    mock_agent = MagicMock()
    mock_agent.ask.return_value = RecruitmentAgentAnswer(
        answer="ok",
        model="mock",
        tool_names_called=[],
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = lambda: mock_agent
    try:
        response = client.post(
            "/api/v1/ai/recruitment/ask",
            json={"question": "Any open jobs?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_recruitment.get_recruitment_agent, None)
    assert response.status_code == 200
