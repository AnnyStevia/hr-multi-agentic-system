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


@dataclass(frozen=True)
class LLMTextResponse:
    content: str
    model: str


@dataclass(frozen=True)
class LLMStructuredResponse:
    data: dict[str, Any]
    model: str


@dataclass(frozen=True)
class LLMToolResponse:
    content: str | None
    tool_calls: tuple[ToolCall, ...]
    model: str


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
