"""Integration: Onboarding Agent ask/confirm endpoints + mocked agent."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.agents.onboarding.schemas import (
    OnboardingAgentAnswer,
    PendingConfirmationInfo,
)
from app.api.v1 import ai_onboarding
from app.tests.helpers import auth_header, create_user_with_role


def test_ask_requires_auth(client):
    response = client.post(
        "/api/v1/ai/onboarding/ask",
        json={"question": "What is my onboarding status?"},
    )
    assert response.status_code == 401


def test_confirm_requires_auth(client):
    response = client.post(
        "/api/v1/ai/onboarding/confirm",
        json={"confirmation_token": "x" * 20},
    )
    assert response.status_code == 401


def test_employee_can_ask_onboarding_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.onboard.ai@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.onboard.ai@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = OnboardingAgentAnswer(
        answer="Your onboarding is in progress.",
        model="mock",
        tool_names_called=["get_my_onboarding"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/onboarding/ask",
            json={"question": "What is my onboarding status?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tool_names_called"] == ["get_my_onboarding"]
    assert body["pending_confirmation"] is None
    assert set(body.keys()) <= {
        "answer",
        "model",
        "tool_names_called",
        "usage",
        "pending_confirmation",
    }


def test_ask_response_can_include_pending_confirmation(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.onboard.pending@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.onboard.pending@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = OnboardingAgentAnswer(
        answer="Please confirm acknowledging the policy task.",
        model="mock",
        tool_names_called=["acknowledge_onboarding_task"],
        usage=None,
        pending_confirmation=PendingConfirmationInfo(
            token="tok1234567890",
            tool_name="acknowledge_onboarding_task",
            summary="Acknowledge task 7",
            expires_at=9999999999,
        ),
    )
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/onboarding/ask",
            json={"question": "Acknowledge the company policy task."},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pending_confirmation"]["tool_name"] == "acknowledge_onboarding_task"
    assert body["pending_confirmation"]["token"] == "tok1234567890"


def test_confirm_with_mocked_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.onboard.confirm@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.onboard.confirm@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.confirm.return_value = OnboardingAgentAnswer(
        answer="Confirmed and completed: acknowledge_onboarding_task.",
        model="confirmed-action",
        tool_names_called=["acknowledge_onboarding_task"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/onboarding/confirm",
            json={"confirmation_token": "tok1234567890"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pending_confirmation"] is None
    assert body["tool_names_called"] == ["acknowledge_onboarding_task"]
    mock_agent.confirm.assert_called_once()


def test_hr_can_ask_onboarding_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.onboard.ai@test.com",
        password="hrpass123",
        role_name="hr",
    )
    headers = auth_header(
        client, email="hr.onboard.ai@test.com", password="hrpass123"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = OnboardingAgentAnswer(
        answer="There are 2 employees in onboarding.",
        model="mock",
        tool_names_called=["list_onboardings"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/onboarding/ask",
            json={"question": "Show me employees currently in onboarding."},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)
    assert response.status_code == 200, response.text
    assert response.json()["tool_names_called"] == ["list_onboardings"]


def test_manager_ask_soft_denial_does_not_leak_onboarding_payload(client, db_session):
    """HTTP is authenticated-only; HR tool denial is at the tool layer."""
    create_user_with_role(
        db_session,
        email="mgr.onboard.ai@test.com",
        password="mgrpass123",
        role_name="manager",
    )
    headers = auth_header(
        client, email="mgr.onboard.ai@test.com", password="mgrpass123"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = OnboardingAgentAnswer(
        answer="You are not authorized to view other employees' onboarding.",
        model="mock",
        tool_names_called=[],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/onboarding/ask",
            json={"question": "Show me Sarah's onboarding."},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    mock_agent.ask.assert_called_once()
    assert body.get("pending_confirmation") is None
    assert body.get("tool_names_called") == []
    assert "not authorized" in body["answer"].lower()


def test_candidate_can_reach_ask_endpoint_authenticated(client, db_session):
    create_user_with_role(
        db_session,
        email="cand.onboard.ai@test.com",
        password="pass12345",
        role_name="candidate",
    )
    headers = auth_header(
        client, email="cand.onboard.ai@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = OnboardingAgentAnswer(
        answer="No onboarding record is available for your account.",
        model="mock",
        tool_names_called=[],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_onboarding.get_onboarding_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/onboarding/ask",
            json={"question": "What is my onboarding status?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_onboarding.get_onboarding_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pending_confirmation"] is None
    assert body["tool_names_called"] == []
