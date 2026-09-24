from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    # Provider-specific payload (e.g. Gemini Content with thought signatures).
    native_content: Any | None = None


@dataclass(frozen=True)
class LLMUsage:
    """Token usage reported by a provider response (when available)."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMTextResponse:
    content: str
    model: str
    usage: LLMUsage | None = None


@dataclass(frozen=True)
class LLMStructuredResponse:
    data: dict[str, Any]
    model: str
    usage: LLMUsage | None = None


@dataclass(frozen=True)
class LLMToolResponse:
    content: str | None
    tool_calls: tuple[ToolCall, ...]
    model: str
    usage: LLMUsage | None = None
    native_content: Any | None = None


class LLMProvider(ABC):
    """Provider-agnostic LLM contract for later agents/orchestration."""

    @abstractmethod
    def generate_text(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMTextResponse:
        raise NotImplementedError

    @abstractmethod
    def generate_structured(
        self,
        messages: Sequence[LLMMessage],
        *,
        schema: dict[str, Any],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMStructuredResponse:
        raise NotImplementedError

    @abstractmethod
    def generate_with_tools(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[ToolDefinition],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tool_choice: str = "auto",
    ) -> LLMToolResponse:
        raise NotImplementedError
