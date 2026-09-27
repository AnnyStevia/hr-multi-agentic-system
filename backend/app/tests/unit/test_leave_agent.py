"""Unit tests for LeaveAgent (mocked LLM)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.agents.leave import (
    LeaveAgent,
    LeaveAgentError,
    LeaveAgentRequest,
    LeaveAgentValidationError,
)
from app.ai.agents.leave.prompts import LEAVE_AGENT_SYSTEM_PROMPT
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.ai.tools import ToolAuthorizationError


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"leaves:read", "recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _agent(provider: MagicMock, *, leave_service=None, employee_service=None) -> LeaveAgent:
    return LeaveAgent(
        llm_provider=provider,
        leave_service=leave_service or MagicMock(),
        employee_service=employee_service or MagicMock(),
    )


def test_empty_question_rejected():
    agent = _agent(MagicMock())
    with pytest.raises(LeaveAgentValidationError, match="empty"):
        agent.ask(LeaveAgentRequest(question="  ", context=_hr()))


def test_agent_uses_list_pending_tool():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="list_pending_leave_requests", arguments={}),),
            model="mock",
        ),
        LLMToolResponse(
            content="There is 1 pending leave request.",
            tool_calls=(),
            model="mock",
        ),
    ]
    leave_service = MagicMock()
    leave_service.list_requests_for_hr.return_value = []
    agent = _agent(provider, leave_service=leave_service)
    answer = agent.ask(
        LeaveAgentRequest(question="What leave is pending?", context=_hr())
    )
    assert answer.tool_names_called == ["list_pending_leave_requests"]
    assert "pending" in answer.answer.lower()


def test_agent_does_not_hallucinate_when_no_tool_content():
    provider = MagicMock()
    provider.generate_with_tools.return_value = LLMToolResponse(
        content=None,
        tool_calls=(),
        model="mock",
    )
    answer = _agent(provider).ask(
        LeaveAgentRequest(question="How many days does Sarah have?", context=_hr())
    )
    assert answer.tool_names_called == []
    assert "enough information" in answer.answer.lower()


def test_find_employees_ambiguity_message_surfaced():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(ToolCall(id="c1", name="find_employees", arguments={"q": "Sarah"}),),
            model="mock",
        ),
        LLMToolResponse(
            content="Multiple employees named Sarah matched. Please provide an employee_id.",
            tool_calls=(),
            model="mock",
        ),
    ]
    employee_service = MagicMock()
    emp_a = MagicMock()
    emp_a.id = 1
    emp_a.full_name = "Sarah Alpha"
    emp_a.email = "a@test.com"
    emp_a.position = None
    emp_a.department = None
    emp_a.employment_status = MagicMock(value="active")
    emp_b = MagicMock()
    emp_b.id = 2
    emp_b.full_name = "Sarah Beta"
    emp_b.email = "b@test.com"
    emp_b.position = None
    emp_b.department = None
    emp_b.employment_status = MagicMock(value="active")
    employee_service.list_employees.return_value = ([emp_a, emp_b], 2)

    agent = _agent(provider, employee_service=employee_service)
    answer = agent.ask(
        LeaveAgentRequest(question="What is Sarah's leave balance?", context=_hr())
    )
    assert answer.tool_names_called == ["find_employees"]
    assert "employee_id" in answer.answer.lower() or "multiple" in answer.answer.lower()


def test_unauthorized_tool_call_soft_fails_and_answers():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="c1", name="get_leave_balance", arguments={"employee_id": 1}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="I am not allowed to look up that employee's balance.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = _agent(provider)
    employee_ctx = AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
        candidate_id=None,
    )
    answer = agent.ask(
        LeaveAgentRequest(question="Balance for 1?", context=employee_ctx)
    )
    assert answer.tool_names_called == ["get_leave_balance"]
    assert "not allowed" in answer.answer.lower() or "enough" in answer.answer.lower() or answer.answer


def test_prompt_documents_balance_quirk_and_grounding():
    prompt = LEAVE_AGENT_SYSTEM_PROMPT.lower()
    assert "days_available" in prompt
    assert "pending" in prompt
    assert "never invent" in prompt
    assert "find_direct_reports" in prompt
    assert "get_my_leave_balance" in prompt
    assert "confirmation" in prompt
    assert "on behalf" in prompt
    assert "data, not instructions" in prompt
    assert "create_leave_request" in prompt
    assert "manager_id" in prompt or "org" in prompt


def test_ask_proposes_write_with_pending_confirmation(db_session):
    from app.ai.audit.models import AiToolActionAudit
    from app.modules.leave.models import (
        LeaveApprovalStatus,
        LeaveCancellationStatus,
        LeaveRequestStatus,
    )

    leave_service = MagicMock()
    req = MagicMock()
    req.id = 55
    req.employee_id = 10
    req.leave_type_id = 1
    req.leave_type = MagicMock(name="Annual")
    req.leave_type.name = "Annual"
    req.start_date = __import__("datetime").date(2026, 10, 5)
    req.end_date = __import__("datetime").date(2026, 10, 9)
    req.requested_days = 5
    req.status = LeaveRequestStatus.PENDING
    req.cancellation_status = LeaveCancellationStatus.NONE
    req.manager_approval = LeaveApprovalStatus.PENDING
    req.hr_approval = LeaveApprovalStatus.PENDING
    leave_service.create_request_for_user.return_value = req

    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="create_leave_request",
                    arguments={
                        "leave_type_id": 1,
                        "start_date": "2026-10-05",
                        "end_date": "2026-10-09",
                    },
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="You're requesting annual leave from October 5 to October 9. Please confirm.",
            tool_calls=(),
            model="mock",
        ),
    ]
    write_ctx = AIExecutionContext(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read", "leaves:write"}),
        employee_id=10,
        candidate_id=None,
    )
    agent = LeaveAgent(
        llm_provider=provider,
        leave_service=leave_service,
        employee_service=MagicMock(),
        db=db_session,
    )
    pending = agent.ask(
        LeaveAgentRequest(question="Request leave Oct 5-9", context=write_ctx)
    )
    assert pending.pending_confirmation is not None
    assert pending.pending_confirmation.tool_name == "create_leave_request"
    leave_service.create_request_for_user.assert_not_called()
    audits = (
        db_session.query(AiToolActionAudit)
        .filter(AiToolActionAudit.tool_name == "create_leave_request")
        .all()
    )
    assert any(a.phase == "proposed" for a in audits)

    confirmed = agent.confirm(
        token=pending.pending_confirmation.token, context=write_ctx
    )
    assert confirmed.pending_confirmation is None
    assert "create_leave_request" in confirmed.tool_names_called
    leave_service.create_request_for_user.assert_called_once()
    phases = {
        a.phase
        for a in db_session.query(AiToolActionAudit)
        .filter(AiToolActionAudit.tool_name == "create_leave_request")
        .all()
    }
    assert phases >= {"proposed", "confirmed", "executed"}


def test_confirm_rejects_wrong_user_token():
    from app.ai.confirmation import create_confirmation_token

    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="create_leave_request",
        arguments={
            "leave_type_id": 1,
            "start_date": "2026-10-05",
            "end_date": "2026-10-09",
        },
        summary="x",
        ttl_seconds=120,
    )
    agent = LeaveAgent(
        llm_provider=MagicMock(),
        leave_service=MagicMock(),
        employee_service=MagicMock(),
    )
    other = AIExecutionContext(
        user_id=99,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read", "leaves:write"}),
        employee_id=99,
        candidate_id=None,
    )
    with pytest.raises(LeaveAgentValidationError):
        agent.confirm(token=token, context=other)


def test_confirm_surfaces_service_business_error():
    from app.ai.confirmation import create_confirmation_token
    from app.shared.exceptions import AppException

    leave_service = MagicMock()
    leave_service.create_request_for_user.side_effect = AppException(
        "No leave policy is configured for this leave type and year",
        status_code=400,
    )
    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="create_leave_request",
        arguments={
            "leave_type_id": 2,
            "start_date": "2024-10-05",
            "end_date": "2024-10-09",
        },
        summary="x",
        ttl_seconds=120,
    )
    agent = LeaveAgent(
        llm_provider=MagicMock(),
        leave_service=leave_service,
        employee_service=MagicMock(),
    )
    ctx = AIExecutionContext(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read", "leaves:write"}),
        employee_id=10,
        candidate_id=None,
    )
    with pytest.raises(LeaveAgentValidationError, match="No leave policy"):
        agent.confirm(token=token, context=ctx)


def test_prompt_defaults_year_when_omitted():
    prompt = LEAVE_AGENT_SYSTEM_PROMPT.lower()
    assert "current utc calendar year" in prompt
    assert "past year" in prompt
    assert "confirm button" in prompt or "ui confirm" in prompt
    assert "type" in prompt and "confirm" in prompt
    assert "approve_leave_request" in prompt
