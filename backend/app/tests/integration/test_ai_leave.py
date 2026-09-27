"""Integration: Leave Agent ask endpoint auth + mocked agent."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.agents.leave.schemas import LeaveAgentAnswer
from app.api.v1 import ai_leave
from app.tests.helpers import auth_header, create_user_with_role


def test_ask_requires_auth(client):
    response = client.post("/api/v1/ai/leave/ask", json={"question": "Who is on leave?"})
    assert response.status_code == 401


def test_candidate_cannot_ask_leave_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="cand.leave.ai@test.com",
        password="pass12345",
        role_name="candidate",
    )
    headers = auth_header(client, email="cand.leave.ai@test.com", password="pass12345")
    response = client.post(
        "/api/v1/ai/leave/ask",
        json={"question": "Who is on leave?"},
        headers=headers,
    )
    assert response.status_code == 403


def test_employee_cannot_ask_leave_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.leave.ai@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(client, email="emp.leave.ai@test.com", password="pass12345")
    response = client.post(
        "/api/v1/ai/leave/ask",
        json={"question": "List pending leave"},
        headers=headers,
    )
    assert response.status_code == 403


def test_manager_cannot_ask_leave_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="mgr.leave.ai@test.com",
        password="mgrpass123",
        role_name="manager",
    )
    headers = auth_header(client, email="mgr.leave.ai@test.com", password="mgrpass123")
    response = client.post(
        "/api/v1/ai/leave/ask",
        json={"question": "Who is on leave?"},
        headers=headers,
    )
    assert response.status_code == 403


def test_hr_ask_leave_returns_answer(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.leave.ai@test.com",
        password="hrpass123",
        role_name="hr",
        first_name="Amina",
        last_name="HR",
    )
    headers = auth_header(client, email="hr.leave.ai@test.com", password="hrpass123")

    mock_agent = MagicMock()
    mock_agent.ask.return_value = LeaveAgentAnswer(
        answer="Nobody is currently on leave.",
        model="mock",
        tool_names_called=["list_currently_on_leave"],
        usage=None,
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_agent
    try:
        response = client.post(
            "/api/v1/ai/leave/ask",
            json={"question": "Who is on leave today?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "Nobody is currently on leave."
    assert body["tool_names_called"] == ["list_currently_on_leave"]
    assert body["model"] == "mock"
