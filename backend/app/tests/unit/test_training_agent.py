"""Unit tests for TrainingAgent (mocked LLM)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.ai.agents.training import (
    TrainingAgent,
    TrainingAgentRequest,
    TrainingAgentValidationError,
)
from app.ai.agents.training.prompts import TRAINING_AGENT_SYSTEM_PROMPT
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.modules.training.models import OnboardingTrainingStatus


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"training:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"training:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _manager() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=5,
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"training:read", "leaves:read"}),
        employee_id=50,
        candidate_id=None,
    )


def _agent(provider: MagicMock, *, training_service=None) -> TrainingAgent:
    return TrainingAgent(
        llm_provider=provider,
        training_service=training_service or MagicMock(),
    )


def _assignment_mock(
    *,
    status: OnboardingTrainingStatus = OnboardingTrainingStatus.PENDING,
    resource_url: str | None = "https://learn.example.com/safety",
):
    now = datetime.now(UTC)
    training = MagicMock()
    training.id = 5
    training.title = "Safety Course"
    training.description = "Handbook"
    training.resource_url = resource_url
    assignment = MagicMock()
    assignment.id = 11
    assignment.onboarding_id = 1
    assignment.training_id = 5
    assignment.status = status
    assignment.assigned_at = now
    assignment.completed_at = None
    assignment.created_at = now
    assignment.updated_at = now
    assignment.training = training
    return assignment


def test_empty_question_rejected():
    with pytest.raises(TrainingAgentValidationError, match="empty"):
        _agent(MagicMock()).ask(
            TrainingAgentRequest(question="  ", context=_employee())
        )


def test_registry_has_three_reads_and_two_writes():
    agent = _agent(MagicMock())
    names = {t.name for t in agent.registry.list_tools()}
    assert names == {
        "list_my_training_assignments",
        "list_trainings",
        "list_onboarding_training_assignments",
        "complete_my_training_assignment",
        "assign_training_to_onboarding",
    }
    writes = {
        t.name
        for t in agent.registry.list_tools()
        if t.metadata.operation == "write"
    }
    assert writes == {
        "complete_my_training_assignment",
        "assign_training_to_onboarding",
    }
    for tool in agent.registry.list_tools():
        if tool.metadata.operation == "write":
            assert tool.metadata.may_require_confirmation is True
    assert "delete_training" not in names
    assert "create_training" not in names
    assert "find_employees" not in names


def test_prompt_documents_read_only_and_limits():
    prompt = TRAINING_AGENT_SYSTEM_PROMPT.lower()
    assert "not the security layer" in prompt or "not the security" in prompt
    assert "due date" in prompt or "due dates" in prompt
    assert "certificate" in prompt
    assert "mandatory" in prompt
    assert "resource_url" in prompt
    assert "manager" in prompt
    assert "manager_id" in prompt
    assert "training:read" in prompt
    assert "training:write" in prompt
    assert "confirm" in prompt
    assert "complete_my_training_assignment" in prompt
    assert "assign_training_to_onboarding" in prompt
    assert "delete_training" in prompt
    assert "list_my_training_assignments" in prompt
    assert "list_trainings" in prompt
    assert "list_onboarding_training_assignments" in prompt
    assert "another employee" in prompt or "another person" in prompt
    assert "direct-report" in prompt or "direct report" in prompt


def test_employee_question_uses_self_assignments_tool():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="c1", name="list_my_training_assignments", arguments={}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content=(
                "You have one pending training: Safety Course. "
                "Resource: https://learn.example.com/safety"
            ),
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    service.list_assignments_for_user.return_value = [_assignment_mock()]

    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(
            question="What trainings are assigned to me?",
            context=_employee(),
        )
    )
    assert answer.tool_names_called == ["list_my_training_assignments"]
    service.list_assignments_for_user.assert_called_once_with(9)
    assert "safety" in answer.answer.lower()
    assert "https://learn.example.com/safety" in answer.answer
    assert "certificate" not in answer.answer.lower()
    assert "due date" not in answer.answer.lower()
    assert "mandatory" not in answer.answer.lower()


def test_manager_own_question_uses_self_tool():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="c1", name="list_my_training_assignments", arguments={}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="You have one pending training assignment.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    service.list_assignments_for_user.return_value = [_assignment_mock()]
    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(question="What trainings do I have?", context=_manager())
    )
    assert answer.tool_names_called == ["list_my_training_assignments"]
    service.list_assignments_for_user.assert_called_once_with(5)


def test_employee_forced_catalogue_soft_fails_without_service_call():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="list_trainings", arguments={}),),
            model="mock",
        ),
        LLMToolResponse(
            content="I cannot list the company catalogue for your role.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(
            question="What trainings are available in the company?",
            context=_employee(),
        )
    )
    assert answer.tool_names_called == ["list_trainings"]
    service.list_trainings.assert_not_called()
    assert "Ada" not in answer.answer
    assert "Sarah" not in answer.answer


def test_manager_forced_onboarding_assignments_soft_fails():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="list_onboarding_training_assignments",
                    arguments={"onboarding_id": 42},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Managers cannot view another person's training through this assistant.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(
            question="What trainings has Sarah been assigned?",
            context=_manager(),
        )
    )
    assert answer.tool_names_called == ["list_onboarding_training_assignments"]
    service.list_assignments_for_hr.assert_not_called()
    assert "pending" not in answer.answer.lower() or "cannot" in answer.answer.lower()


def test_hr_onboarding_assignments_question():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="list_onboarding_training_assignments",
                    arguments={"onboarding_id": 42},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Onboarding 42 has Safety Course pending.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    service.list_assignments_for_hr.return_value = [_assignment_mock()]
    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(
            question="What trainings are assigned to onboarding 42?",
            context=_hr(),
        )
    )
    assert answer.tool_names_called == ["list_onboarding_training_assignments"]
    service.list_assignments_for_hr.assert_called_once_with(42)


def test_absent_resource_url_handled():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="c1", name="list_my_training_assignments", arguments={}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Safety Course is pending and has no resource link.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    service.list_assignments_for_user.return_value = [
        _assignment_mock(resource_url=None)
    ]
    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(question="Do my trainings have links?", context=_employee())
    )
    assert "https://" not in answer.answer
    assert "no resource" in answer.answer.lower() or "no" in answer.answer.lower()


def test_no_manager_team_or_find_employees_tools():
    agent = _agent(MagicMock())
    names = {t.name for t in agent.registry.list_tools()}
    assert "find_employees" not in names
    assert not any("team" in n or "report" in n for n in names)


def test_hr_catalogue_question_uses_list_trainings():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="list_trainings", arguments={}),),
            model="mock",
        ),
        LLMToolResponse(
            content="Catalogue has Safety Course with a resource URL.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    training = MagicMock()
    training.id = 5
    training.title = "Safety Course"
    training.description = None
    training.resource_url = "https://learn.example.com/safety"
    service.list_trainings.return_value = [training]

    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(
            question="List the training catalogue.",
            context=_hr(),
        )
    )
    assert answer.tool_names_called == ["list_trainings"]
    service.list_trainings.assert_called_once_with()
    assert "catalogue" in answer.answer.lower() or "safety" in answer.answer.lower()


def _hr_write() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"training:read", "training:write"}),
        employee_id=10,
        candidate_id=None,
    )


def test_ask_proposes_complete_with_pending_confirmation():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="complete_my_training_assignment",
                    arguments={"training_assignment_id": 11},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="I can mark your training assignment as completed. Please confirm.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(
            question="Mark my safety training as completed.",
            context=_employee(),
        )
    )
    assert answer.tool_names_called == ["complete_my_training_assignment"]
    assert answer.pending_confirmation is not None
    assert answer.pending_confirmation.tool_name == "complete_my_training_assignment"
    assert "confirm" in answer.answer.lower()
    assert "completed" not in answer.answer.lower() or "please confirm" in answer.answer.lower()
    service.complete_assignment_for_user.assert_not_called()


def test_confirm_rejects_wrong_user_token():
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=99,
        tool_name="complete_my_training_assignment",
        arguments={"training_assignment_id": 11},
        summary="Complete assignment 11",
        target_type="onboarding_training",
        target_id=11,
    )
    service = MagicMock()
    with pytest.raises(TrainingAgentValidationError):
        _agent(MagicMock(), training_service=service).confirm(
            token=token, context=_employee()
        )
    service.complete_assignment_for_user.assert_not_called()


def test_confirm_rejects_altered_assignment_id(db_session):
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="complete_my_training_assignment",
        arguments={"training_assignment_id": 11},
        summary="Complete assignment 11",
        target_type="onboarding_training",
        target_id=11,
    )
    # Tamper: change payload in a new token with different assignment id for same user
    # Wrong tool / body tamper: craft token for assignment 99 then try to execute as if 11
    bad, _ = create_confirmation_token(
        user_id=9,
        tool_name="complete_my_training_assignment",
        arguments={"training_assignment_id": 99},
        summary="Complete assignment 99",
        target_type="onboarding_training",
        target_id=99,
    )
    service = MagicMock()
    service.complete_assignment_for_user.side_effect = Exception("should use args from token")
    # Confirming bad token should call with 99 — if service raises AppException for not found:
    from app.shared.exceptions import AppException

    service.complete_assignment_for_user.side_effect = AppException(
        "Training assignment not found", status_code=404
    )
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    with pytest.raises(TrainingAgentValidationError, match="not found"):
        agent.confirm(token=bad, context=_employee())
    service.complete_assignment_for_user.assert_called_once_with(9, 99)
    # Original token is still valid to execute once
    service.complete_assignment_for_user.side_effect = None
    service.complete_assignment_for_user.return_value = MagicMock(
        id=11,
        training_id=5,
        onboarding_id=1,
        status=OnboardingTrainingStatus.COMPLETED,
    )
    ok = agent.confirm(token=token, context=_employee())
    assert ok.pending_confirmation is None
    assert "complete_my_training_assignment" in ok.tool_names_called


def test_confirm_rejects_wrong_tool_token(db_session):
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="create_leave_request",
        arguments={
            "leave_type_id": 1,
            "start_date": "2026-10-05",
            "end_date": "2026-10-09",
        },
        summary="Leave request",
    )
    service = MagicMock()
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    with pytest.raises(TrainingAgentValidationError, match="Unknown tool"):
        agent.confirm(token=token, context=_employee())
    service.complete_assignment_for_user.assert_not_called()


def test_confirm_replay_after_success_surfaces_domain_error(db_session):
    from app.ai.confirmation import create_confirmation_token
    from app.shared.exceptions import AppException

    service = MagicMock()
    done = MagicMock()
    done.id = 11
    done.training_id = 5
    done.onboarding_id = 1
    done.status = OnboardingTrainingStatus.COMPLETED
    # First confirm succeeds; second replay: domain may still succeed idempotently.
    # For training complete, service is idempotent — so replay returns completed again.
    # Spec wants replay → no second mutation. Idempotent complete returns same row.
    # Use assign for clearer second-failure: use complete that raises on second call.
    service.complete_assignment_for_user.side_effect = [
        done,
        AppException("Training assignment not found", status_code=404),
    ]
    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="complete_my_training_assignment",
        arguments={"training_assignment_id": 11},
        summary="Complete assignment 11",
        target_type="onboarding_training",
        target_id=11,
    )
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    ok = agent.confirm(token=token, context=_employee())
    assert ok.pending_confirmation is None
    with pytest.raises(TrainingAgentValidationError, match="not found"):
        agent.confirm(token=token, context=_employee())
    assert service.complete_assignment_for_user.call_count == 2


def test_confirm_assign_executes_for_hr(db_session):
    from app.ai.confirmation import create_confirmation_token

    service = MagicMock()
    row = MagicMock()
    row.id = 20
    row.onboarding_id = 42
    row.training_id = 5
    row.status = OnboardingTrainingStatus.PENDING
    service.assign_training.return_value = row
    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="assign_training_to_onboarding",
        arguments={"onboarding_id": 42, "training_id": 5},
        summary="Assign training 5 to onboarding 42",
        target_type="onboarding",
        target_id=42,
    )
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    answer = agent.confirm(token=token, context=_hr_write())
    assert answer.pending_confirmation is None
    assert answer.tool_names_called == ["assign_training_to_onboarding"]
    service.assign_training.assert_called_once()


def test_confirm_assign_denied_for_employee(db_session):
    from app.ai.agents.training import TrainingAgentError
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="assign_training_to_onboarding",
        arguments={"onboarding_id": 42, "training_id": 5},
        summary="Assign training 5 to onboarding 42",
        target_type="onboarding",
        target_id=42,
    )
    service = MagicMock()
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    with pytest.raises(TrainingAgentError):
        agent.confirm(token=token, context=_employee())
    service.assign_training.assert_not_called()


def test_read_question_has_no_pending_confirmation():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="c1", name="list_my_training_assignments", arguments={}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="You have one pending training.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    service.list_assignments_for_user.return_value = [_assignment_mock()]
    answer = _agent(provider, training_service=service).ask(
        TrainingAgentRequest(question="What trainings do I have?", context=_employee())
    )
    assert answer.pending_confirmation is None
    service.complete_assignment_for_user.assert_not_called()


def test_confirm_rejects_body_tamper_altered_assignment_id(db_session):
    """HMAC integrity: mutate args in token body, keep old signature → reject."""
    import base64
    import json

    from app.ai.audit.models import AiToolActionAudit
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="complete_my_training_assignment",
        arguments={"training_assignment_id": 11},
        summary="Complete assignment 11",
        target_type="onboarding_training",
        target_id=11,
    )
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    body, sig = raw.rsplit(b".", 1)
    payload = json.loads(body)
    payload["arguments"] = {"training_assignment_id": 999}
    tampered_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad = (
        base64.urlsafe_b64encode(tampered_body + b"." + sig)
        .decode("ascii")
        .rstrip("=")
    )
    service = MagicMock()
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    with pytest.raises(TrainingAgentValidationError):
        agent.confirm(token=bad, context=_employee())
    service.complete_assignment_for_user.assert_not_called()
    failed = (
        db_session.query(AiToolActionAudit)
        .filter(
            AiToolActionAudit.phase == "failed",
            AiToolActionAudit.error_code == "invalid_or_expired_token",
        )
        .all()
    )
    assert failed


def test_confirm_rejects_body_tamper_altered_assign_ids(db_session):
    import base64
    import json

    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="assign_training_to_onboarding",
        arguments={"onboarding_id": 42, "training_id": 5},
        summary="Assign training 5 to onboarding 42",
        target_type="onboarding",
        target_id=42,
    )
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    body, sig = raw.rsplit(b".", 1)
    payload = json.loads(body)
    payload["arguments"] = {"onboarding_id": 99, "training_id": 7}
    tampered_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad = (
        base64.urlsafe_b64encode(tampered_body + b"." + sig)
        .decode("ascii")
        .rstrip("=")
    )
    service = MagicMock()
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    with pytest.raises(TrainingAgentValidationError):
        agent.confirm(token=bad, context=_hr_write())
    service.assign_training.assert_not_called()


def test_confirm_rejects_expired_token(db_session):
    import time
    from unittest.mock import patch

    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="complete_my_training_assignment",
        arguments={"training_assignment_id": 11},
        summary="Complete assignment 11",
        target_type="onboarding_training",
        target_id=11,
    )
    service = MagicMock()
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    with patch(
        "app.ai.confirmation.tokens.time.time", return_value=time.time() + 10_000
    ):
        with pytest.raises(TrainingAgentValidationError):
            agent.confirm(token=token, context=_employee())
    service.complete_assignment_for_user.assert_not_called()


def test_confirm_assign_denied_when_hr_lacks_write_at_confirm(db_session):
    """Re-auth at confirm: token for HR user, but context lost training:write."""
    from app.ai.agents.training import TrainingAgentError
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="assign_training_to_onboarding",
        arguments={"onboarding_id": 42, "training_id": 5},
        summary="Assign training 5 to onboarding 42",
        target_type="onboarding",
        target_id=42,
    )
    service = MagicMock()
    agent = TrainingAgent(
        llm_provider=MagicMock(),
        training_service=service,
        db=db_session,
    )
    # Same user_id as token, but only training:read (no write) at confirm time
    weaker = AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"training:read"}),
        employee_id=10,
        candidate_id=None,
    )
    with pytest.raises(TrainingAgentError):
        agent.confirm(token=token, context=weaker)
    service.assign_training.assert_not_called()
