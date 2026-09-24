"""Unit tests for BaseTool → ToolDefinition adapter and mock tool roundtrip."""

from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.ai.orchestration import run_tool_roundtrip
from app.ai.tools import (
    GetCurrentAiContextTool,
    ToolAuthorizationError,
    ToolRegistry,
    tool_to_definition,
)


def _context(
    *,
    user_id: int = 42,
    role_names: frozenset[str] | None = None,
    permission_names: frozenset[str] | None = None,
    employee_id: int | None = 7,
    candidate_id: int | None = None,
) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=role_names if role_names is not None else frozenset({"employee"}),
        permission_names=(
            permission_names
            if permission_names is not None
            else frozenset({"leaves:read"})
        ),
        employee_id=employee_id,
        candidate_id=candidate_id,
    )


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GetCurrentAiContextTool())
    return registry


def test_tool_to_definition_for_smoke_tool():
    tool = GetCurrentAiContextTool()
    definition = tool_to_definition(tool)

    assert definition.name == "get_current_ai_context"
    assert "authenticated" in definition.description.lower() or "context" in definition.description.lower()
    assert definition.parameters.get("type") == "object"
    assert isinstance(definition.parameters.get("properties"), dict)
    assert "$schema" not in definition.parameters
    assert "$defs" not in definition.parameters


def test_roundtrip_auth_success_with_mock_provider():
    tool = GetCurrentAiContextTool()
    # Spy: wrap execute to detect calls
    original_execute = tool.execute
    calls: list[object] = []

    def tracked_execute(context, args):
        calls.append(args)
        return original_execute(context, args)

    tool.execute = tracked_execute  # type: ignore[method-assign]

    registry = ToolRegistry()
    registry.register(tool)

    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="call_1", name="get_current_ai_context", arguments={}),
            ),
            model="mock-model",
        ),
        LLMToolResponse(
            content="You are user 42 with role employee.",
            tool_calls=(),
            model="mock-model",
        ),
    ]

    result = run_tool_roundtrip(
        provider=provider,
        context=_context(user_id=42, employee_id=7),
        registry=registry,
        user_prompt="What is my AI context?",
    )

    assert len(calls) == 1
    assert result.tool_names_called == ("get_current_ai_context",)
    assert result.tool_results[0].success is True
    assert result.tool_results[0].data == {
        "user_id": 42,
        "roles": ["employee"],
        "employee_id": 7,
        "candidate_id": None,
    }
    assert "42" in result.final_content
    assert result.model == "mock-model"
    assert provider.generate_with_tools.call_count == 2

    second_kwargs = provider.generate_with_tools.call_args_list[1]
    second_messages = second_kwargs.args[0] if second_kwargs.args else second_kwargs.kwargs["messages"]
    tool_msgs = [m for m in second_messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "call_1"
    assert '"user_id": 42' in (tool_msgs[0].content or "")


def test_roundtrip_auth_reject_before_execution():
    tool = GetCurrentAiContextTool()
    original_execute = tool.execute
    executed = {"count": 0}

    def tracked_execute(context, args):
        executed["count"] += 1
        return original_execute(context, args)

    tool.execute = tracked_execute  # type: ignore[method-assign]

    registry = ToolRegistry()
    registry.register(tool)

    provider = MagicMock()
    provider.generate_with_tools.return_value = LLMToolResponse(
        content=None,
        tool_calls=(
            ToolCall(id="call_deny", name="get_current_ai_context", arguments={}),
        ),
        model="mock-model",
    )

    unauthorized = _context(
        permission_names=frozenset(),  # missing leaves:read
        role_names=frozenset({"candidate"}),
    )

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        run_tool_roundtrip(
            provider=provider,
            context=unauthorized,
            registry=registry,
            user_prompt="Show my context",
        )

    assert executed["count"] == 0
    # First LLM call only — no tool result round-trip
    assert provider.generate_with_tools.call_count == 1
