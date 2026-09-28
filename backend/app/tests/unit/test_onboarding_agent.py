"""Unit tests for OnboardingAgent (mocked LLM)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.ai.agents.onboarding import (
    OnboardingAgent,
    OnboardingAgentRequest,
    OnboardingAgentValidationError,
)
from app.ai.agents.onboarding.prompts import ONBOARDING_AGENT_SYSTEM_PROMPT
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.ai.tools.find_employees import FindEmployeesTool
from app.modules.onboarding.models import OnboardingStatus
from app.modules.onboarding.schemas import (
    DocumentCountResponse,
    OnboardingProgressResponse,
    ProgressCountResponse,
)


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"onboarding:read", "recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _manager() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=5,
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=50,
        candidate_id=None,
    )


def _agent(
    provider: MagicMock, *, onboarding_service=None, employee_service=None
) -> OnboardingAgent:
    return OnboardingAgent(
        llm_provider=provider,
        onboarding_service=onboarding_service or MagicMock(),
        employee_service=employee_service or MagicMock(),
    )


def test_empty_question_rejected():
    with pytest.raises(OnboardingAgentValidationError, match="empty"):
        _agent(MagicMock()).ask(
            OnboardingAgentRequest(question="  ", context=_employee())
        )


def test_registry_has_exactly_three_write_tools_and_no_manager_tools():
    agent = _agent(MagicMock())
    names = {t.name for t in agent.registry.list_tools()}
    assert "get_my_onboarding" in names
    assert "list_onboardings" in names
    assert "find_employees" in names
    assert "acknowledge_onboarding_task" in names
    assert "complete_manual_onboarding_task" in names
    assert "complete_onboarding" in names
    assert "list_team_onboardings" not in names
    write_names = {
        n
        for n in names
        if "complete" in n or "acknowledge" in n or n.endswith("_write")
    }
    assert write_names == {
        "acknowledge_onboarding_task",
        "complete_manual_onboarding_task",
        "complete_onboarding",
    }
    manager_like = [n for n in names if "team" in n or "report" in n]
    assert manager_like == []


def test_prompt_documents_manager_and_recruitment_limits():
    prompt = ONBOARDING_AGENT_SYSTEM_PROMPT.lower()
    assert "manager_id" in prompt or "org chart" in prompt
    assert "recruitment:read" in prompt
    assert "not the security layer" in prompt or "not the security" in prompt
    assert "direct report" in prompt
    assert "confirm" in prompt
    assert "acknowledge_onboarding_task" in prompt


def test_find_employees_in_registry_still_requires_recruitment_read():
    agent = _agent(MagicMock())
    tool = next(t for t in agent.registry.list_tools() if t.name == "find_employees")
    assert isinstance(tool, FindEmployeesTool)
    assert "recruitment:read" in tool.metadata.required_permissions


def test_employee_status_uses_get_my_onboarding():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="get_my_onboarding", arguments={}),),
            model="mock",
        ),
        LLMToolResponse(
            content="Your onboarding is in progress.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    now = datetime.now(UTC)
    ob = MagicMock()
    ob.id = 1
    ob.employee_id = 99
    ob.status = OnboardingStatus.IN_PROGRESS
    ob.started_at = now
    ob.completed_at = None
    ob.created_at = now
    ob.updated_at = now
    service.get_for_employee_user.return_value = ob

    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="What is my onboarding status?", context=_employee()
        )
    )
    assert answer.tool_names_called == ["get_my_onboarding"]
    service.get_for_employee_user.assert_called_once_with(9)
    assert "progress" in answer.answer.lower() or "onboarding" in answer.answer.lower()


def test_employee_forced_hr_tool_soft_fails_without_calling_hr_service():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="list_onboardings", arguments={}),),
            model="mock",
        ),
        LLMToolResponse(
            content="I cannot list organizational onboardings for your role.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="List all employees in onboarding.", context=_employee()
        )
    )
    assert answer.tool_names_called == ["list_onboardings"]
    service.list_for_hr.assert_not_called()
    service.get_by_employee_id_for_hr.assert_not_called()
    assert "Ada" not in answer.answer


def test_employee_forced_get_by_employee_soft_fails():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="get_onboarding_by_employee",
                    arguments={"employee_id": 42},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="You are not authorized to view another employee's onboarding.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="Show employee 42 onboarding.", context=_employee()
        )
    )
    assert answer.tool_names_called == ["get_onboarding_by_employee"]
    service.get_by_employee_id_for_hr.assert_not_called()


def test_manager_forced_hr_tool_soft_fails():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="get_onboarding_by_employee",
                    arguments={"employee_id": 99},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Managers cannot view reports' onboarding through this assistant.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="Show my direct report's onboarding.", context=_manager()
        )
    )
    assert answer.tool_names_called == ["get_onboarding_by_employee"]
    service.get_by_employee_id_for_hr.assert_not_called()
    service.list_for_hr.assert_not_called()


def test_hr_list_onboardings_tool():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="list_onboardings", arguments={}),),
            model="mock",
        ),
        LLMToolResponse(
            content="There is 1 employee currently in onboarding.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    service.list_for_hr.return_value = []
    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="Show me employees currently in onboarding.", context=_hr()
        )
    )
    assert answer.tool_names_called == ["list_onboardings"]
    service.list_for_hr.assert_called_once()


def test_no_tool_content_safe_fallback():
    provider = MagicMock()
    provider.generate_with_tools.return_value = LLMToolResponse(
        content=None,
        tool_calls=(),
        model="mock",
    )
    answer = _agent(provider).ask(
        OnboardingAgentRequest(question="Anything?", context=_employee())
    )
    assert answer.tool_names_called == []
    assert "enough information" in answer.answer.lower()


def test_progress_tool_does_not_invent_completion():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="c1", name="get_my_onboarding_progress", arguments={}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="You are 33% through required onboarding tasks. Onboarding is still in progress.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    service.get_progress_for_employee_user.return_value = OnboardingProgressResponse(
        onboarding_id=1,
        status=OnboardingStatus.IN_PROGRESS,
        completed_at=None,
        tasks=ProgressCountResponse(total=3, completed=1, pending=2),
        required_tasks=ProgressCountResponse(total=2, completed=1, pending=1),
        optional_tasks=ProgressCountResponse(total=1, completed=0, pending=1),
        trainings=ProgressCountResponse(total=0, completed=0, pending=0),
        documents=DocumentCountResponse(total=0),
        overall_percentage=33,
    )
    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="How far along am I in my onboarding?", context=_employee()
        )
    )
    assert answer.tool_names_called == ["get_my_onboarding_progress"]
    assert "33" in answer.answer or "progress" in answer.answer.lower()
    assert answer.pending_confirmation is None


def test_read_question_has_no_pending_confirmation():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="get_my_onboarding", arguments={}),),
            model="mock",
        ),
        LLMToolResponse(
            content="Your onboarding is in progress.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    now = datetime.now(UTC)
    ob = MagicMock()
    ob.id = 1
    ob.employee_id = 99
    ob.status = OnboardingStatus.IN_PROGRESS
    ob.started_at = now
    ob.completed_at = None
    ob.created_at = now
    ob.updated_at = now
    service.get_for_employee_user.return_value = ob
    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="What is my onboarding status?", context=_employee()
        )
    )
    assert answer.pending_confirmation is None
    service.acknowledge_task_for_employee.assert_not_called()


def test_ask_proposes_ack_with_pending_confirmation(db_session):
    from app.ai.audit.models import AiToolActionAudit
    from app.modules.onboarding.models import OnboardingTaskStatus

    service = MagicMock()
    task = MagicMock()
    task.id = 7
    task.onboarding_id = 1
    task.status = OnboardingTaskStatus.COMPLETED
    service.acknowledge_task_for_employee.return_value = task

    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="acknowledge_onboarding_task",
                    arguments={"task_id": 7},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Please confirm acknowledging the company policy task.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = OnboardingAgent(
        llm_provider=provider,
        onboarding_service=service,
        employee_service=MagicMock(),
        db=db_session,
    )
    pending = agent.ask(
        OnboardingAgentRequest(
            question="Acknowledge the company policy task.", context=_employee()
        )
    )
    assert pending.pending_confirmation is not None
    assert pending.pending_confirmation.tool_name == "acknowledge_onboarding_task"
    service.acknowledge_task_for_employee.assert_not_called()
    audits = (
        db_session.query(AiToolActionAudit)
        .filter(AiToolActionAudit.tool_name == "acknowledge_onboarding_task")
        .all()
    )
    assert any(a.phase == "proposed" for a in audits)

    confirmed = agent.confirm(
        token=pending.pending_confirmation.token, context=_employee()
    )
    assert confirmed.pending_confirmation is None
    assert "acknowledge_onboarding_task" in confirmed.tool_names_called
    service.acknowledge_task_for_employee.assert_called_once_with(9, 7)
    phases = {
        a.phase
        for a in db_session.query(AiToolActionAudit)
        .filter(AiToolActionAudit.tool_name == "acknowledge_onboarding_task")
        .all()
    }
    assert phases >= {"proposed", "confirmed", "executed"}


def test_confirm_rejects_wrong_user_token():
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="acknowledge_onboarding_task",
        arguments={"task_id": 7},
        summary="Acknowledge task 7",
        target_type="onboarding_task",
        target_id=7,
    )
    other = AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset(),
        employee_id=99,
        candidate_id=None,
    )
    with pytest.raises(OnboardingAgentValidationError):
        _agent(MagicMock()).confirm(token=token, context=other)


def test_confirm_rejects_altered_arguments():
    from app.ai.confirmation import ConfirmationError, create_confirmation_token, verify_confirmation_token

    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="acknowledge_onboarding_task",
        arguments={"task_id": 7},
        summary="Acknowledge task 7",
        target_type="onboarding_task",
        target_id=7,
    )
    payload = verify_confirmation_token(token, user_id=9)
    # Tamper would fail HMAC at verify; assert bound args match
    assert payload.arguments == {"task_id": 7}
    with pytest.raises(ConfirmationError):
        verify_confirmation_token(token + "x", user_id=9)


def test_confirm_rejects_body_tamper_altered_task_id(db_session):
    import base64
    import json

    from app.ai.audit.models import AiToolActionAudit
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="acknowledge_onboarding_task",
        arguments={"task_id": 7},
        summary="Acknowledge task 7",
        target_type="onboarding_task",
        target_id=7,
    )
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    body, sig = raw.rsplit(b".", 1)
    payload = json.loads(body)
    payload["arguments"] = {"task_id": 999}
    tampered_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad = (
        base64.urlsafe_b64encode(tampered_body + b"." + sig)
        .decode("ascii")
        .rstrip("=")
    )
    service = MagicMock()
    agent = OnboardingAgent(
        llm_provider=MagicMock(),
        onboarding_service=service,
        employee_service=MagicMock(),
        db=db_session,
    )
    with pytest.raises(OnboardingAgentValidationError):
        agent.confirm(token=bad, context=_employee())
    service.acknowledge_task_for_employee.assert_not_called()
    failed = (
        db_session.query(AiToolActionAudit)
        .filter(
            AiToolActionAudit.phase == "failed",
            AiToolActionAudit.error_code == "invalid_or_expired_token",
        )
        .all()
    )
    assert failed


def test_confirm_rejects_wrong_tool_token(db_session):
    from app.ai.audit.models import AiToolActionAudit
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
    agent = OnboardingAgent(
        llm_provider=MagicMock(),
        onboarding_service=service,
        employee_service=MagicMock(),
        db=db_session,
    )
    with pytest.raises(OnboardingAgentValidationError, match="Unknown tool"):
        agent.confirm(token=token, context=_employee())
    service.acknowledge_task_for_employee.assert_not_called()
    failed = (
        db_session.query(AiToolActionAudit)
        .filter(
            AiToolActionAudit.tool_name == "create_leave_request",
            AiToolActionAudit.phase == "failed",
            AiToolActionAudit.error_code == "unknown_tool",
        )
        .all()
    )
    assert failed


def test_confirm_replay_after_success_surfaces_domain_error(db_session):
    from app.ai.audit.models import AiToolActionAudit
    from app.ai.confirmation import create_confirmation_token
    from app.modules.onboarding.models import OnboardingTaskStatus
    from app.shared.exceptions import AppException

    service = MagicMock()
    task = MagicMock()
    task.id = 7
    task.onboarding_id = 1
    task.status = OnboardingTaskStatus.COMPLETED
    service.acknowledge_task_for_employee.side_effect = [
        task,
        AppException("Task is already completed", status_code=400),
    ]
    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="acknowledge_onboarding_task",
        arguments={"task_id": 7},
        summary="Acknowledge task 7",
        target_type="onboarding_task",
        target_id=7,
    )
    agent = OnboardingAgent(
        llm_provider=MagicMock(),
        onboarding_service=service,
        employee_service=MagicMock(),
        db=db_session,
    )
    ok = agent.confirm(token=token, context=_employee())
    assert ok.pending_confirmation is None
    with pytest.raises(OnboardingAgentValidationError, match="already completed"):
        agent.confirm(token=token, context=_employee())
    assert service.acknowledge_task_for_employee.call_count == 2
    failed = (
        db_session.query(AiToolActionAudit)
        .filter(
            AiToolActionAudit.tool_name == "acknowledge_onboarding_task",
            AiToolActionAudit.phase == "failed",
            AiToolActionAudit.error_code == "execution",
        )
        .all()
    )
    assert failed


def test_confirm_surfaces_service_business_error():
    from app.ai.confirmation import create_confirmation_token
    from app.shared.exceptions import AppException

    service = MagicMock()
    service.acknowledge_task_for_employee.side_effect = AppException(
        "Only acknowledgement tasks can be acknowledged by the employee",
        status_code=400,
    )
    token, _ = create_confirmation_token(
        user_id=9,
        tool_name="acknowledge_onboarding_task",
        arguments={"task_id": 7},
        summary="Acknowledge task 7",
        target_type="onboarding_task",
        target_id=7,
    )
    agent = OnboardingAgent(
        llm_provider=MagicMock(),
        onboarding_service=service,
        employee_service=MagicMock(),
    )
    with pytest.raises(OnboardingAgentValidationError, match="acknowledgement"):
        agent.confirm(token=token, context=_employee())


def test_prompt_documents_write_intent_boundaries():
    prompt = ONBOARDING_AGENT_SYSTEM_PROMPT.lower()
    assert "what happens if i acknowledge" in prompt
    assert "should i complete" in prompt
    assert "can you acknowledge this task" in prompt
    assert "pending confirmation is not execution" in prompt or "pending confirmation is not" in prompt
    assert "confirm button" in prompt or "ui confirm" in prompt


def test_employee_forced_complete_onboarding_soft_fails():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="complete_onboarding",
                    arguments={"onboarding_id": 1},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="You are not authorized to complete onboarding.",
            tool_calls=(),
            model="mock",
        ),
    ]
    service = MagicMock()
    answer = _agent(provider, onboarding_service=service).ask(
        OnboardingAgentRequest(
            question="Complete onboarding 1.", context=_employee()
        )
    )
    assert answer.tool_names_called == ["complete_onboarding"]
    assert answer.pending_confirmation is None
    service.complete_for_hr.assert_not_called()
