"""Minimal LLM ↔ tool executor roundtrip (smoke / early orchestration)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMMessage, LLMProvider, LLMUsage, ToolCall
from app.ai.tools.executor import ToolExecutor
from app.ai.tools.llm_adapter import tool_to_definition
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.schemas import ToolResult

_DEFAULT_SYSTEM = (
    "You are a helpful assistant for an HR system smoke test. "
    "When the user asks about their identity or context, call the "
    "get_current_ai_context tool. Do not invent user_id or roles."
)

_GEMINI_SMOKE_PROMPT = "Call get_current_ai_context once."
_LEAVE_BALANCE_SMOKE_PROMPT = "Call get_my_leave_balance once."


@dataclass(frozen=True)
class ToolRoundtripResult:
    final_content: str
    model: str
    tool_names_called: tuple[str, ...]
    tool_results: tuple[ToolResult, ...]
    usage: LLMUsage | None = None


def run_tool_roundtrip(
    *,
    provider: LLMProvider,
    context: AIExecutionContext,
    registry: ToolRegistry,
    user_prompt: str,
    system_prompt: str | None = _DEFAULT_SYSTEM,
    tool_choice: str = "any",
    max_tokens: int | None = None,
    max_tool_calls: int = 8,
) -> ToolRoundtripResult:
    """One tool-calling round: LLM → ToolExecutor (auth) → LLM final answer.

    Authorization failures from ToolExecutor propagate (tool is not re-invoked
    and results are not sent back to the LLM).
    """
    tools = [tool_to_definition(tool) for tool in registry.list_tools()]
    messages: list[LLMMessage] = []
    if system_prompt:
        messages.append(LLMMessage(role="system", content=system_prompt))
    messages.append(LLMMessage(role="user", content=user_prompt))

    first = provider.generate_with_tools(
        messages,
        tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
    )

    if not first.tool_calls:
        return ToolRoundtripResult(
            final_content=first.content or "",
            model=first.model,
            tool_names_called=(),
            tool_results=(),
            usage=first.usage,
        )

    executor = ToolExecutor(registry)
    tool_results: list[ToolResult] = []
    tool_names: list[str] = []

    messages.append(
        LLMMessage(
            role="assistant",
            content=first.content,
            tool_calls=first.tool_calls,
            native_content=first.native_content,
        )
    )

    for call in first.tool_calls[: max(1, max_tool_calls)]:
        result = executor.execute(context, call.name, call.arguments)
        tool_results.append(result)
        tool_names.append(call.name)
        messages.append(_tool_result_message(call, result))

    second = provider.generate_with_tools(
        messages,
        tools,
        tool_choice="none",
        max_tokens=max_tokens,
    )

    return ToolRoundtripResult(
        final_content=second.content or "",
        model=second.model,
        tool_names_called=tuple(tool_names),
        tool_results=tuple(tool_results),
        usage=_merge_usage(first.usage, second.usage),
    )


def run_controlled_gemini_smoke(
    *,
    provider: LLMProvider,
    context: AIExecutionContext,
    registry: ToolRegistry,
    user_prompt: str = _GEMINI_SMOKE_PROMPT,
) -> ToolRoundtripResult:
    """Low-cost Gemini smoke: short user prompt, thinking LOW, one tool, two API calls."""
    return run_tool_roundtrip(
        provider=provider,
        context=context,
        registry=registry,
        user_prompt=user_prompt,
        system_prompt=None,
        tool_choice="any",
        max_tokens=512,
        max_tool_calls=1,
    )


def run_controlled_leave_balance_smoke(
    *,
    provider: LLMProvider,
    context: AIExecutionContext,
    registry: ToolRegistry,
    user_prompt: str = _LEAVE_BALANCE_SMOKE_PROMPT,
) -> ToolRoundtripResult:
    """Controlled smoke for get_my_leave_balance (one tool, short prompt, max 512 tokens)."""
    return run_tool_roundtrip(
        provider=provider,
        context=context,
        registry=registry,
        user_prompt=user_prompt,
        system_prompt=None,
        tool_choice="any",
        max_tokens=512,
        max_tool_calls=1,
    )


def _tool_result_message(call: ToolCall, result: ToolResult) -> LLMMessage:
    payload = result.data if result.data is not None else {"error": result.error}
    return LLMMessage(
        role="tool",
        name=call.name,
        tool_call_id=call.id,
        content=json.dumps(payload),
    )


def _merge_usage(first: LLMUsage | None, second: LLMUsage | None) -> LLMUsage | None:
    if first is None and second is None:
        return None
    if first is None:
        return second
    if second is None:
        return first

    def _sum(a: int | None, b: int | None) -> int | None:
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    return LLMUsage(
        input_tokens=_sum(first.input_tokens, second.input_tokens),
        output_tokens=_sum(first.output_tokens, second.output_tokens),
        thinking_tokens=_sum(first.thinking_tokens, second.thinking_tokens),
        total_tokens=_sum(first.total_tokens, second.total_tokens),
    )
