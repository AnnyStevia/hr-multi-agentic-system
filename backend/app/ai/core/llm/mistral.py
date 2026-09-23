from __future__ import annotations

import json
from typing import Any, Sequence

from mistralai import Mistral
from mistralai.models import Function, JSONSchema, ResponseFormat, Tool

from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMStructuredResponse,
    LLMTextResponse,
    LLMToolResponse,
    ToolCall,
    ToolDefinition,
)


class MistralLLMProvider(LLMProvider):
    """Mistral chat completions adapter behind the LLMProvider interface."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: Any | None = None,
    ):
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("MISTRAL_API_KEY is required")
        if not model or not model.strip():
            raise LLMConfigurationError("MISTRAL_MODEL is required")
        self._model = model.strip()
        self._client = client if client is not None else Mistral(api_key=api_key.strip())

    def generate_text(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMTextResponse:
        response = self._complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = _first_choice(response)
        content = _extract_text(getattr(choice.message, "content", None))
        return LLMTextResponse(content=content, model=_response_model(response, self._model))

    def generate_structured(
        self,
        messages: Sequence[LLMMessage],
        *,
        schema: dict[str, Any],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMStructuredResponse:
        if not schema:
            raise LLMConfigurationError("A JSON schema is required for structured output")
        schema_name = str(schema.get("title") or schema.get("name") or "response")
        response_format = ResponseFormat(
            type="json_schema",
            json_schema=JSONSchema(
                name=schema_name,
                schema_definition=schema,
                strict=True,
            ),
        )
        response = self._complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        choice = _first_choice(response)
        raw = _extract_text(getattr(choice.message, "content", None))
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise LLMProviderError("Mistral returned invalid JSON for structured output") from exc
        if not isinstance(data, dict):
            raise LLMProviderError("Mistral structured output must be a JSON object")
        return LLMStructuredResponse(
            data=data,
            model=_response_model(response, self._model),
        )

    def generate_with_tools(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[ToolDefinition],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tool_choice: str = "auto",
    ) -> LLMToolResponse:
        mistral_tools = [
            Tool(
                type="function",
                function=Function(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters,
                ),
            )
            for tool in tools
        ]
        response = self._complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=mistral_tools or None,
            tool_choice=tool_choice,
        )
        choice = _first_choice(response)
        message = choice.message
        content = _extract_text(getattr(message, "content", None)) or None
        tool_calls = tuple(_parse_tool_call(item) for item in (message.tool_calls or []))
        return LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            model=_response_model(response, self._model),
        )

    def _complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None,
        max_tokens: int | None,
        response_format: ResponseFormat | None = None,
        tools: list[Tool] | None = None,
        tool_choice: str | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [_to_mistral_message(message) for message in messages],
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        try:
            return self._client.chat.complete(**kwargs)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"Mistral chat completion failed: {exc}") from exc


def _to_mistral_message(message: LLMMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role}
    if message.content is not None:
        payload["content"] = message.content
    if message.name is not None:
        payload["name"] = message.name
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in message.tool_calls
        ]
    return payload


def _first_choice(response: Any) -> Any:
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise LLMProviderError("Mistral returned no choices")
    return choices[0]


def _response_model(response: Any, fallback: str) -> str:
    model = getattr(response, "model", None)
    return str(model) if model else fallback


def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text") is not None:
                parts.append(str(item["text"]))
            else:
                text = getattr(item, "text", None)
                if text is not None:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


def _parse_tool_call(item: Any) -> ToolCall:
    function = getattr(item, "function", None)
    name = getattr(function, "name", "") if function is not None else ""
    raw_arguments = getattr(function, "arguments", "{}") if function is not None else "{}"
    if isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        try:
            parsed = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Mistral tool call arguments were not valid JSON for tool '{name}'"
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMProviderError(
                f"Mistral tool call arguments must be a JSON object for tool '{name}'"
            )
        arguments = parsed
    return ToolCall(
        id=str(getattr(item, "id", "") or ""),
        name=str(name),
        arguments=arguments,
    )
