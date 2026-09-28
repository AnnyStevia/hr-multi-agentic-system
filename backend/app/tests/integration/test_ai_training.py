"""Integration: Training Agent ask/confirm endpoints + mocked agent."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.agents.training.exceptions import TrainingAgentError, TrainingAgentValidationError
from app.ai.agents.training.schemas import PendingConfirmationInfo, TrainingAgentAnswer
from app.api.v1 import ai_training
from app.tests.helpers import auth_header, create_user_with_role


def test_ask_requires_auth(client):
    response = client.post(
        "/api/v1/ai/training/ask",
        json={"question": "What trainings are assigned to me?"},
    )
    assert response.status_code == 401


def test_confirm_requires_auth(client):
    response = client.post(
        "/api/v1/ai/training/confirm",
        json={"confirmation_token": "x" * 20},
    )
    assert response.status_code == 401


def test_employee_can_ask_training_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.train.ai@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.train.ai@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = TrainingAgentAnswer(
        answer="You have one pending training assignment.",
        model="mock",
        tool_names_called=["list_my_training_assignments"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/training/ask",
            json={"question": "What trainings are assigned to me?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tool_names_called"] == ["list_my_training_assignments"]
    assert body["answer"] == "You have one pending training assignment."
    assert body["pending_confirmation"] is None
    assert set(body.keys()) == {
        "answer",
        "model",
        "tool_names_called",
        "usage",
        "pending_confirmation",
    }
    assert "traceback" not in response.text.lower()
    assert "sqlalchemy" not in response.text.lower()


def test_ask_response_can_include_pending_confirmation(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.train.pending@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.train.pending@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = TrainingAgentAnswer(
        answer="I can mark your training assignment as completed. Please confirm.",
        model="mock",
        tool_names_called=["complete_my_training_assignment"],
        usage=None,
        pending_confirmation=PendingConfirmationInfo(
            token="tok1234567890",
            tool_name="complete_my_training_assignment",
            summary="Complete assignment 11",
            expires_at=9999999999,
        ),
    )
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/training/ask",
            json={"question": "Mark my safety training completed."},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pending_confirmation"]["tool_name"] == "complete_my_training_assignment"
    assert body["pending_confirmation"]["token"] == "tok1234567890"


def test_confirm_with_mocked_agent(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.train.confirm@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.train.confirm@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.confirm.return_value = TrainingAgentAnswer(
        answer="Confirmed and completed: complete_my_training_assignment.",
        model="confirmed-action",
        tool_names_called=["complete_my_training_assignment"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/training/confirm",
            json={"confirmation_token": "tok1234567890abcd"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pending_confirmation"] is None
    assert body["tool_names_called"] == ["complete_my_training_assignment"]
    mock_agent.confirm.assert_called_once()


def test_ask_validation_error_is_422(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.train.validation@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.train.validation@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.side_effect = TrainingAgentValidationError("Question must not be empty")
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/training/ask",
            json={"question": "x"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
    assert response.status_code == 422
    assert response.json()["detail"] == "Question must not be empty"
    assert "traceback" not in response.text.lower()


def test_ask_agent_error_is_controlled_502(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.train.fail@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.train.fail@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.side_effect = TrainingAgentError("internal boom with secret detail")
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/training/ask",
            json={"question": "List my trainings"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Unable to answer the training question right now."
    )
    assert "secret detail" not in response.text
    assert "traceback" not in response.text.lower()


def test_confirm_validation_error_is_409(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.train.confirmfail@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.train.confirmfail@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.confirm.side_effect = TrainingAgentValidationError(
        "Confirmation token is invalid or expired"
    )
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/training/confirm",
            json={"confirmation_token": "tok1234567890abcd"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
    assert response.status_code == 409
    assert "invalid" in response.json()["detail"].lower()


def test_manager_ask_soft_denial_envelope(client, db_session):
    create_user_with_role(
        db_session,
        email="mgr.train.ai@test.com",
        password="pass12345",
        role_name="manager",
    )
    headers = auth_header(
        client, email="mgr.train.ai@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = TrainingAgentAnswer(
        answer="I can only show your own training assignments, not a teammate's.",
        model="mock",
        tool_names_called=["list_my_training_assignments"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_training.get_training_agent] = (
        lambda: mock_agent
    )
    try:
        response = client.post(
            "/api/v1/ai/training/ask",
            json={"question": "What trainings has my report been assigned?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_training.get_training_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "own" in body["answer"].lower() or "cannot" in body["answer"].lower()
    assert "traceback" not in response.text.lower()
    assert "sqlalchemy" not in response.text.lower()
