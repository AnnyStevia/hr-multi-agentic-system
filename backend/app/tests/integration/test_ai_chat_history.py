"""Integration: persistent chat history around unified ask + CRUD + confirm resolve."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.agents.leave.schemas import LeaveAgentAnswer, PendingConfirmationInfo
from app.ai.history.models import AiConversationMessage
from app.ai.history.sanitize import token_digest
from app.api.v1 import ai_knowledge, ai_leave, ai_recruitment
from app.tests.helpers import auth_header, create_user_with_role


def _mock_leave_ok(answer: str = "Balance is fine.", pending=None):
    mock = MagicMock()
    mock.ask.return_value = LeaveAgentAnswer(
        answer=answer,
        model="mock-leave",
        tool_names_called=["get_my_leave_balance"],
        usage=None,
        pending_confirmation=pending,
    )
    return mock


def test_ask_creates_conversation_and_ids(client, db_session):
    create_user_with_role(
        db_session,
        email="hist.ask.create@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="hist.ask.create@test.com", password="pass12345"
    )
    mock_leave = _mock_leave_ok()
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
    assert body["conversation_id"] is not None
    assert body["message_id"] is not None
    assert body["answer"] == "Balance is fine."

    detail = client.get(
        f"/api/v1/ai/conversations/{body['conversation_id']}", headers=headers
    )
    assert detail.status_code == 200, detail.text
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["id"] == body["message_id"]
    assert "pending_token_digest" not in messages[1]
    assert messages[1].get("pending") is None


def test_ask_continues_same_conversation(client, db_session):
    create_user_with_role(
        db_session,
        email="hist.ask.cont@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="hist.ask.cont@test.com", password="pass12345"
    )
    mock_leave = _mock_leave_ok("First")
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: MagicMock()
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: MagicMock()
    )
    try:
        first = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "What's my remaining annual leave?"},
            headers=headers,
        )
        assert first.status_code == 200, first.text
        cid = first.json()["conversation_id"]
        mock_leave.ask.return_value = LeaveAgentAnswer(
            answer="Second",
            model="mock-leave",
            tool_names_called=[],
            usage=None,
            pending_confirmation=None,
        )
        second = client.post(
            "/api/v1/ai/assistant/ask",
            json={
                "message": "And sick leave balance?",
                "conversation_id": cid,
            },
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )

    assert second.status_code == 200, second.text
    assert second.json()["conversation_id"] == cid
    detail = client.get(f"/api/v1/ai/conversations/{cid}", headers=headers)
    assert len(detail.json()["messages"]) == 4


def test_foreign_conversation_id_returns_404(client, db_session):
    owner = create_user_with_role(
        db_session,
        email="hist.idor.owner@test.com",
        password="pass12345",
        role_name="employee",
    )
    create_user_with_role(
        db_session,
        email="hist.idor.other@test.com",
        password="pass12345",
        role_name="employee",
    )
    owner_headers = auth_header(
        client, email="hist.idor.owner@test.com", password="pass12345"
    )
    other_headers = auth_header(
        client, email="hist.idor.other@test.com", password="pass12345"
    )
    mock_leave = _mock_leave_ok()
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: MagicMock()
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: MagicMock()
    )
    try:
        created = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "What's my remaining annual leave?"},
            headers=owner_headers,
        )
        assert created.status_code == 200
        cid = created.json()["conversation_id"]

        ask_foreign = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "What's my remaining annual leave?", "conversation_id": cid},
            headers=other_headers,
        )
        get_foreign = client.get(
            f"/api/v1/ai/conversations/{cid}", headers=other_headers
        )
        delete_foreign = client.delete(
            f"/api/v1/ai/conversations/{cid}", headers=other_headers
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )

    assert ask_foreign.status_code == 404
    assert get_foreign.status_code == 404
    assert delete_foreign.status_code == 404
    # Owner can still see it
    assert (
        client.get(f"/api/v1/ai/conversations/{cid}", headers=owner_headers).status_code
        == 200
    )
    assert owner.id is not None


def test_pending_stored_as_digest_response_keeps_live_token(client, db_session):
    create_user_with_role(
        db_session,
        email="hist.pending.api@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="hist.pending.api@test.com", password="pass12345"
    )
    live_token = "live-hmac-token-for-response-only"
    mock_leave = _mock_leave_ok(
        "Please confirm",
        pending=PendingConfirmationInfo(
            token=live_token,
            tool_name="create_leave_request",
            summary="Create annual leave",
            expires_at=9999999999,
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
            json={"message": "Create leave for me next week"},
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
    assert body["pending_confirmation"]["token"] == live_token

    msg = db_session.get(AiConversationMessage, body["message_id"])
    assert msg is not None
    assert msg.pending_token_digest == token_digest(live_token)
    assert msg.pending_resolved is False
    assert live_token not in (msg.content or "")

    detail = client.get(
        f"/api/v1/ai/conversations/{body['conversation_id']}", headers=headers
    )
    pending = detail.json()["messages"][-1]["pending"]
    assert pending["summary"] == "Create annual leave"
    assert "token" not in pending
    assert "digest" not in str(pending).lower()


def test_confirm_resolves_pending_and_succeeds_without_history_row(
    client, db_session
):
    create_user_with_role(
        db_session,
        email="hist.confirm@test.com",
        password="pass12345",
        role_name="hr",
    )
    headers = auth_header(
        client, email="hist.confirm@test.com", password="pass12345"
    )
    live_token = "confirm-resolve-token-xyz"
    mock_leave = _mock_leave_ok(
        "Confirm please",
        pending=PendingConfirmationInfo(
            token=live_token,
            tool_name="create_leave_request",
            summary="Create",
            expires_at=9999999999,
        ),
    )
    mock_leave.confirm.return_value = LeaveAgentAnswer(
        answer="Leave created.",
        model="mock-leave",
        tool_names_called=["create_leave_request"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: MagicMock()
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: MagicMock()
    )
    try:
        ask = client.post(
            "/api/v1/ai/assistant/ask",
            json={"message": "Create leave for tomorrow"},
            headers=headers,
        )
        assert ask.status_code == 200, ask.text
        mid = ask.json()["message_id"]

        confirm = client.post(
            "/api/v1/ai/leave/confirm",
            json={"confirmation_token": live_token},
            headers=headers,
        )
        # Confirm without any history row must still succeed
        confirm_orphan = client.post(
            "/api/v1/ai/leave/confirm",
            json={"confirmation_token": "orphan-token-no-history"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)
        client.app.dependency_overrides.pop(
            ai_recruitment.get_recruitment_agent, None
        )

    assert confirm.status_code == 200, confirm.text
    db_session.expire_all()
    row = db_session.get(AiConversationMessage, mid)
    assert row is not None
    assert row.pending_resolved is True

    assert confirm_orphan.status_code == 200, confirm_orphan.text


def test_list_and_delete_conversations(client, db_session):
    create_user_with_role(
        db_session,
        email="hist.crud@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="hist.crud@test.com", password="pass12345"
    )
    mock_leave = _mock_leave_ok()
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_leave
    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = (
        lambda: MagicMock()
    )
    client.app.dependency_overrides[ai_recruitment.get_recruitment_agent] = (
        lambda: MagicMock()
    )
    try:
        ask = client.post(
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

    cid = ask.json()["conversation_id"]
    listing = client.get("/api/v1/ai/conversations", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == cid for item in listing.json())

    deleted = client.delete(f"/api/v1/ai/conversations/{cid}", headers=headers)
    assert deleted.status_code == 204
    assert (
        client.get(f"/api/v1/ai/conversations/{cid}", headers=headers).status_code
        == 404
    )
