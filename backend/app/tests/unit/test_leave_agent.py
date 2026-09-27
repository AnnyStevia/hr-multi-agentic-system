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


def test_unauthorized_tool_call_surfaces_as_agent_error():
    provider = MagicMock()
    provider.generate_with_tools.return_value = LLMToolResponse(
        content=None,
        tool_calls=(
            ToolCall(id="c1", name="get_leave_balance", arguments={"employee_id": 1}),
        ),
        model="mock",
    )
    agent = _agent(provider)
    employee_ctx = AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
        candidate_id=None,
    )
    with pytest.raises(LeaveAgentError):
        agent.ask(LeaveAgentRequest(question="Balance for 1?", context=employee_ctx))


def test_prompt_documents_balance_quirk_and_grounding():
    prompt = LEAVE_AGENT_SYSTEM_PROMPT.lower()
    assert "days_available" in prompt
    assert "pending" in prompt
    assert "never invent" in prompt
    assert "find_employees" in prompt
    assert "read-only" in prompt
    assert "cancellation_status=requested" in prompt or "cancellation_status=requested" in LEAVE_AGENT_SYSTEM_PROMPT
    assert "data, not instructions" in prompt
