"""Unit tests: chat history service ownership, sequence, pending resolve."""

from __future__ import annotations

import pytest

from app.ai.core.context.models import AIExecutionContext
from app.ai.history.models import AiConversation, AiConversationMessage
from app.ai.history.sanitize import token_digest
from app.ai.history.service import ChatHistoryService, ConversationNotFoundError
from app.ai.orchestration.graph.run import OrchestratorResult
from app.tests.helpers import create_user_with_role


def _ctx(user_id: int) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=None,
        candidate_id=None,
    )


def _result(**overrides) -> OrchestratorResult:
    base = dict(
        agent_id="leave",
        answer="You have 5 days.",
        citations=[],
        pending_confirmation=None,
        status="completed",
        model="mock",
        tool_names_called=["get_my_leave_balance"],
        usage=None,
        route_reason="leave_keywords",
        node_path=["filter_available", "select_agent", "invoke_specialist"],
    )
    base.update(overrides)
    return OrchestratorResult(**base)


def test_begin_turn_creates_and_sequences(db_session):
    user = create_user_with_role(
        db_session,
        email="hist.seq@test.com",
        password="pass12345",
        role_name="employee",
    )
    svc = ChatHistoryService(db_session)
    conv, user_msg = svc.begin_turn(
        context=_ctx(user.id), message="Hello history", conversation_id=None
    )
    assert conv.user_id == user.id
    assert user_msg.sequence == 1
    assert user_msg.role == "user"

    assistant = svc.append_assistant_from_result(conversation=conv, result=_result())
    assert assistant.sequence == 2
    assert assistant.role == "assistant"
    assert assistant.pending_token_digest is None
    db_session.commit()

    conv2, user_msg2 = svc.begin_turn(
        context=_ctx(user.id), message="Follow up", conversation_id=conv.id
    )
    assert conv2.id == conv.id
    assert user_msg2.sequence == 3
    db_session.commit()


def test_foreign_conversation_not_found(db_session):
    owner = create_user_with_role(
        db_session,
        email="hist.owner@test.com",
        password="pass12345",
        role_name="employee",
    )
    other = create_user_with_role(
        db_session,
        email="hist.other@test.com",
        password="pass12345",
        role_name="employee",
    )
    svc = ChatHistoryService(db_session)
    conv, _ = svc.begin_turn(
        context=_ctx(owner.id), message="Private", conversation_id=None
    )
    db_session.commit()

    with pytest.raises(ConversationNotFoundError):
        svc.begin_turn(
            context=_ctx(other.id), message="Nope", conversation_id=conv.id
        )

    with pytest.raises(ConversationNotFoundError):
        svc.get_conversation(conv.id, other.id)


def test_pending_digest_only_never_raw_token(db_session):
    user = create_user_with_role(
        db_session,
        email="hist.pending@test.com",
        password="pass12345",
        role_name="employee",
    )
    svc = ChatHistoryService(db_session)
    conv, _ = svc.begin_turn(
        context=_ctx(user.id), message="Create leave", conversation_id=None
    )
    token = "super-secret-hmac-token-value"
    result = _result(
        pending_confirmation={
            "token": token,
            "tool_name": "create_leave_request",
            "summary": "Create leave",
            "expires_at": 9999999999,
        }
    )
    assistant = svc.append_assistant_from_result(conversation=conv, result=result)
    db_session.commit()

    assert assistant.pending_token_digest == token_digest(token)
    assert assistant.pending_resolved is False
    assert token not in (assistant.content or "")
    assert assistant.pending_token_digest != token

    row = db_session.get(AiConversationMessage, assistant.id)
    assert row is not None
    dumped = str(row.__dict__)
    assert token not in dumped
    assert "super-secret" not in dumped


def test_resolve_pending_ownership_and_no_row(db_session):
    user = create_user_with_role(
        db_session,
        email="hist.resolve@test.com",
        password="pass12345",
        role_name="employee",
    )
    other = create_user_with_role(
        db_session,
        email="hist.resolve.other@test.com",
        password="pass12345",
        role_name="employee",
    )
    svc = ChatHistoryService(db_session)
    conv, _ = svc.begin_turn(
        context=_ctx(user.id), message="Write", conversation_id=None
    )
    token = "confirm-token-abc"
    assistant = svc.append_assistant_from_result(
        conversation=conv,
        result=_result(
            pending_confirmation={
                "token": token,
                "tool_name": "create_leave_request",
                "summary": "Create",
                "expires_at": 1,
            }
        ),
    )
    db_session.commit()

    assert svc.resolve_pending(user_id=user.id, token=token, resolved=True) is True
    db_session.commit()
    db_session.refresh(assistant)
    assert assistant.pending_resolved is True

    assert (
        svc.resolve_pending(user_id=other.id, token=token, resolved=True) is False
    )
    assert (
        svc.resolve_pending(user_id=user.id, token="missing-token", resolved=True)
        is False
    )


def test_delete_cascades_messages(db_session):
    user = create_user_with_role(
        db_session,
        email="hist.cascade@test.com",
        password="pass12345",
        role_name="employee",
    )
    svc = ChatHistoryService(db_session)
    conv, user_msg = svc.begin_turn(
        context=_ctx(user.id), message="Bye", conversation_id=None
    )
    assistant = svc.append_assistant_from_result(conversation=conv, result=_result())
    db_session.commit()
    conv_id = conv.id
    msg_ids = [user_msg.id, assistant.id]

    svc.delete_conversation(conv_id, user.id)
    assert db_session.get(AiConversation, conv_id) is None
    for mid in msg_ids:
        assert db_session.get(AiConversationMessage, mid) is None
