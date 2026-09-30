"""Unit tests for Offboarding Agent (reads + confirmation-gated writes)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.agents.offboarding import (
    OFFBOARDING_AGENT_ID,
    OffboardingAgent,
    OffboardingAgentRequest,
    OffboardingAgentValidationError,
)
from app.ai.agents.offboarding.prompts import OFFBOARDING_AGENT_SYSTEM_PROMPT
from app.ai.core.context import AIExecutionContext
from app.ai.orchestration.tool_roundtrip import ToolRoundtripResult
from app.ai.tools.schemas import ToolResult


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"offboarding:read", "offboarding:write"}),
        employee_id=10,
        candidate_id=None,
    )


def _agent(**kwargs) -> OffboardingAgent:
    return OffboardingAgent(
        llm_provider=MagicMock(),
        offboarding=MagicMock(),
        employees=MagicMock(),
        get_user=kwargs.pop("get_user", lambda _uid: MagicMock()),
        db=kwargs.pop("db", None),
        **kwargs,
    )


def test_agent_registers_reads_and_writes():
    agent = _agent()
    names = set(agent.tool_names())
    assert {
        "find_employees_for_offboarding",
        "get_offboarding_case",
        "get_offboarding_progress",
        "list_offboarding_tasks",
        "get_offboarding_clearance",
        "get_exit_interview",
        "get_offboarding_readiness",
        "complete_offboarding_case",
        "update_offboarding_clearance",
        "update_offboarding_task",
    } <= names
    assert agent.agent_id == OFFBOARDING_AGENT_ID
    assert "deactivate_account" not in names
    assert "skip_offboarding_task" not in names


def test_agent_ask_empty_question():
    agent = _agent()
    with pytest.raises(OffboardingAgentValidationError):
        agent.ask(OffboardingAgentRequest(question="   ", context=_hr()))


def test_agent_ask_roundtrip(monkeypatch):
    agent = _agent()

    def fake_roundtrip(**kwargs):
        assert kwargs["system_prompt"] == OFFBOARDING_AGENT_SYSTEM_PROMPT
        assert "DATA" in kwargs["system_prompt"]
        assert "PROMPT-INJECTION" in kwargs["system_prompt"]
        assert "confirmation" in kwargs["system_prompt"].lower()
        return ToolRoundtripResult(
            final_content="Case is pending clearance.",
            model="test-model",
            tool_names_called=("get_offboarding_case",),
            tool_results=(),
            usage=None,
        )

    monkeypatch.setattr(
        "app.ai.agents.offboarding.agent.run_tool_roundtrip",
        fake_roundtrip,
    )
    answer = agent.ask(
        OffboardingAgentRequest(question="What is the offboarding status?", context=_hr())
    )
    assert answer.answer == "Case is pending clearance."
    assert answer.pending_confirmation is None
    assert answer.tool_names_called == ["get_offboarding_case"]


def test_agent_ask_surfaces_pending_confirmation(monkeypatch):
    agent = _agent()

    def fake_roundtrip(**kwargs):
        return ToolRoundtripResult(
            final_content="",
            model="test-model",
            tool_names_called=("complete_offboarding_case",),
            tool_results=(
                ToolResult(
                    tool_name="complete_offboarding_case",
                    success=True,
                    data={"arguments": {"case_id": 4}, "status": "pending_confirmation"},
                    confirmation_token="tok",
                    confirmation_summary="Complete case 4",
                    confirmation_expires_at=9999999999,
                    may_require_confirmation=True,
                ),
            ),
            usage=None,
        )

    monkeypatch.setattr(
        "app.ai.agents.offboarding.agent.run_tool_roundtrip",
        fake_roundtrip,
    )
    answer = agent.ask(
        OffboardingAgentRequest(question="Complete Sarah's offboarding.", context=_hr())
    )
    assert answer.pending_confirmation is not None
    assert answer.pending_confirmation.token == "tok"
    assert answer.pending_confirmation.tool_name == "complete_offboarding_case"
    assert "Confirm" in answer.answer
