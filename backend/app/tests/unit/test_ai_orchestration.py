"""Unit: LangGraph unified-assistant orchestration (Orc.1–Orc.3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.agents.leave.schemas import LeaveAgentAnswer, PendingConfirmationInfo
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm.base import LLMStructuredResponse
from app.ai.orchestration.graph import SpecialistAgents, run_assistant_orchestration
from app.ai.orchestration.graph.llm_clarify import try_llm_select_agent
from app.ai.orchestration.graph.messages import CLARIFY_ANSWER, NO_AGENTS_ANSWER
from app.ai.orchestration.handoffs import ALLOWLISTED_HANDOFFS, is_handoff_allowed
from app.ai.rag.generation.schemas import Citation, RAGAnswer
from app.ai.registry import (
    KNOWLEDGE_AGENT,
    LEAVE_AGENT,
    OFFBOARDING_AGENT,
)


def _emp_ctx(**kwargs) -> AIExecutionContext:
    base = dict(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset(
            {
                "company_documents:read",
                "leaves:read",
                "onboarding:read",
                "training:read",
                "offboarding:read",
            }
        ),
        employee_id=10,
        candidate_id=None,
    )
    base.update(kwargs)
    return AIExecutionContext(**base)


def _agents(**overrides) -> SpecialistAgents:
    defaults = {
        "knowledge": MagicMock(name="knowledge"),
        "leave": MagicMock(name="leave"),
        "recruitment": MagicMock(name="recruitment"),
        "onboarding": MagicMock(name="onboarding"),
        "training": MagicMock(name="training"),
        "documents": MagicMock(name="documents"),
        "offboarding": MagicMock(name="offboarding"),
    }
    defaults.update(overrides)
    return SpecialistAgents(**defaults)


def test_orchestrator_routes_leave_and_passes_pending_confirmation():
    leave = MagicMock()
    leave.ask.return_value = LeaveAgentAnswer(
        answer="Confirm leave request?",
        model="mock",
        tool_names_called=["propose_leave_request"],
        usage=None,
        pending_confirmation=PendingConfirmationInfo(
            token="tok-abc",
            tool_name="propose_leave_request",
            summary="Request 2 days",
            expires_at=1_700_000_000,
        ),
    )
    agents = _agents(leave=leave)
    result = run_assistant_orchestration(
        message="What's my remaining annual leave?",
        context=_emp_ctx(),
        agents=agents,
        llm_clarify_enabled=False,
    )
    assert result.status == "completed"
    assert result.agent_id == "leave"
    assert result.pending_confirmation is not None
    assert result.pending_confirmation["token"] == "tok-abc"
    assert result.pending_confirmation["tool_name"] == "propose_leave_request"
    assert result.tool_names_called == ["propose_leave_request"]
    leave.ask.assert_called_once()
    agents.knowledge.ask.assert_not_called()
    agents.recruitment.ask.assert_not_called()
    agents.offboarding.ask.assert_not_called()


def test_orchestrator_knowledge_preserves_citations():
    knowledge = MagicMock()
    knowledge.ask.return_value = RAGAnswer(
        query="policy",
        answer="See handbook [1]",
        citations=[
            Citation(
                citation_id=1,
                chunk_id=2,
                company_document_id=3,
                page_start=1,
                page_end=1,
                document_name="Handbook",
                content_hash="a" * 64,
            )
        ],
        has_context=True,
        retrieval_count=1,
        selected_context_count=1,
        model="mock-rag",
        usage=None,
    )
    agents = _agents(knowledge=knowledge)
    result = run_assistant_orchestration(
        message="What is the company leave policy in the handbook?",
        context=_emp_ctx(),
        agents=agents,
        llm_clarify_enabled=False,
    )
    assert result.status == "completed"
    assert result.agent_id == "knowledge"
    assert len(result.citations) == 1
    assert result.citations[0]["company_document_id"] == 3
    assert result.pending_confirmation is None
    knowledge.ask.assert_called_once()
    agents.leave.ask.assert_not_called()


def test_orchestrator_clarify_does_not_invoke_specialists():
    agents = _agents()
    result = run_assistant_orchestration(
        message="help",
        context=_emp_ctx(),
        agents=agents,
        llm_clarify_enabled=False,
    )
    assert result.status == "clarification_required"
    assert result.agent_id is None
    assert result.answer == CLARIFY_ANSWER
    assert result.pending_confirmation is None
    for name in (
        "knowledge",
        "leave",
        "recruitment",
        "onboarding",
        "training",
        "documents",
        "offboarding",
    ):
        getattr(agents, name).ask.assert_not_called()


def test_orchestrator_no_agents_unavailable():
    agents = _agents()
    # Candidate with no permissions → empty availability
    ctx = AIExecutionContext(
        user_id=99,
        role_names=frozenset({"candidate"}),
        permission_names=frozenset(),
        employee_id=None,
        candidate_id=5,
    )
    result = run_assistant_orchestration(
        message="What is my leave balance?",
        context=ctx,
        agents=agents,
        llm_clarify_enabled=False,
    )
    assert result.status == "unavailable"
    assert result.agent_id is None
    assert result.answer == NO_AGENTS_ANSWER
    agents.leave.ask.assert_not_called()


def test_orchestrator_recruitment_unavailable_for_employee():
    agents = _agents()
    result = run_assistant_orchestration(
        message="Shortlist this candidate for the role",
        context=_emp_ctx(),
        agents=agents,
        llm_clarify_enabled=False,
    )
    assert result.status == "unavailable"
    assert result.agent_id is None
    agents.recruitment.ask.assert_not_called()


def test_orchestrator_does_not_aggregate_tools_only_one_specialist():
    leave = MagicMock()
    leave.ask.return_value = LeaveAgentAnswer(
        answer="12 days",
        model="m",
        tool_names_called=["get_my_leave_balance"],
    )
    agents = _agents(leave=leave)
    result = run_assistant_orchestration(
        message="How many leave days do I have left?",
        context=_emp_ctx(),
        agents=agents,
        llm_clarify_enabled=False,
    )
    assert result.agent_id == "leave"
    called = sum(
        1
        for a in (
            agents.knowledge,
            agents.leave,
            agents.recruitment,
            agents.onboarding,
            agents.training,
            agents.documents,
            agents.offboarding,
        )
        if a.ask.called
    )
    assert called == 1


def test_orchestrator_propagates_specialist_exception():
    from app.ai.agents.leave.exceptions import LeaveAgentValidationError

    leave = MagicMock()
    leave.ask.side_effect = LeaveAgentValidationError("bad leave args")
    agents = _agents(leave=leave)
    with pytest.raises(LeaveAgentValidationError, match="bad leave args"):
        run_assistant_orchestration(
            message="What's my remaining annual leave?",
            context=_emp_ctx(),
            agents=agents,
            llm_clarify_enabled=False,
        )


def test_llm_clarify_disabled_keeps_clarify_even_with_provider():
    provider = MagicMock()
    agents = _agents()
    result = run_assistant_orchestration(
        message="help",
        context=_emp_ctx(),
        agents=agents,
        llm_provider=provider,
        llm_clarify_enabled=False,
    )
    assert result.status == "clarification_required"
    provider.generate_structured.assert_not_called()


def test_llm_clarify_enabled_selects_available_agent_only():
    provider = MagicMock()
    provider.generate_structured.return_value = LLMStructuredResponse(
        data={"agent_id": "leave", "confidence": "high"},
        model="mock",
        usage=None,
    )
    leave = MagicMock()
    leave.ask.return_value = LeaveAgentAnswer(answer="ok", model="m")
    agents = _agents(leave=leave)
    # Vague message → deterministic clarify → optional LLM picks leave.
    result = run_assistant_orchestration(
        message="help",
        context=_emp_ctx(),
        agents=agents,
        llm_provider=provider,
        llm_clarify_enabled=True,
    )
    assert result.status == "completed"
    assert result.agent_id == "leave"
    provider.generate_structured.assert_called_once()
    leave.ask.assert_called_once()


def test_llm_clarify_rejects_agent_outside_available():
    provider = MagicMock()
    provider.generate_structured.return_value = LLMStructuredResponse(
        data={"agent_id": "recruitment", "confidence": "high"},
        model="mock",
        usage=None,
    )
    available = [KNOWLEDGE_AGENT, LEAVE_AGENT, OFFBOARDING_AGENT]
    chosen = try_llm_select_agent(
        provider=provider,
        message="help",
        available=available,
    )
    assert chosen is None


def test_llm_clarify_low_confidence_returns_none():
    provider = MagicMock()
    provider.generate_structured.return_value = LLMStructuredResponse(
        data={"agent_id": "leave", "confidence": "low"},
        model="mock",
        usage=None,
    )
    chosen = try_llm_select_agent(
        provider=provider,
        message="help",
        available=[LEAVE_AGENT],
    )
    assert chosen is None


def test_handoff_allowlist_empty_by_default():
    assert ALLOWLISTED_HANDOFFS == frozenset()
    assert not is_handoff_allowed(
        source_agent_id="offboarding",
        target_agent_id="knowledge",
    )


def test_handoff_self_not_allowed():
    assert not is_handoff_allowed(
        source_agent_id="knowledge",
        target_agent_id="knowledge",
    )


def test_node_path_recorded_on_completed_ask():
    leave = MagicMock()
    leave.ask.return_value = LeaveAgentAnswer(answer="12", model="m")
    agents = _agents(leave=leave)
    result = run_assistant_orchestration(
        message="What's my remaining annual leave?",
        context=_emp_ctx(),
        agents=agents,
        llm_clarify_enabled=False,
    )
    assert "filter_available" in result.node_path
    assert "select_agent" in result.node_path
    assert "invoke_specialist" in result.node_path
    assert "normalize_envelope" in result.node_path
    assert "maybe_llm_clarify" not in result.node_path
