"""Gemini LLM provider adapter (google-genai SDK)."""

from __future__ import annotations

import json
from typing import Any, Sequence

from google import genai
from google.genai import types

from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMStructuredResponse,
    LLMTextResponse,
    LLMToolResponse,
    LLMUsage,
    ToolCall,
    ToolDefinition,
)

_TOOL_CHOICE_MAP = {
    "auto": "AUTO",
    "any": "ANY",
    "none": "NONE",
    "required": "ANY",
}


class GeminiLLMProvider(LLMProvider):
    """Gemini generateContent adapter behind the LLMProvider interface."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: Any | None = None,
        thinking_level: str = "low",
    ):
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("GEMINI_API_KEY is required")
        if not model or not model.strip():
            raise LLMConfigurationError("GEMINI_MODEL is required")
        self._model = model.strip()
        self._thinking_level = (thinking_level or "low").strip().lower()
        self._client = client if client is not None else genai.Client(api_key=api_key.strip())

    @property
    def thinking_level(self) -> str:
        return self._thinking_level

    def generate_text(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMTextResponse:
        response = self._generate(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LLMTextResponse(
            content=_extract_text(response),
            model=_response_model(response, self._model),
            usage=_extract_usage(response),
        )

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
        response = self._generate(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        raw = _extract_text(response)
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise LLMProviderError("Gemini returned invalid JSON for structured output") from exc
        if not isinstance(data, dict):
            raise LLMProviderError("Gemini structured output must be a JSON object")
        return LLMStructuredResponse(
            data=data,
            model=_response_model(response, self._model),
            usage=_extract_usage(response),
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
        gemini_tools = [_to_gemini_tool(tool) for tool in tools] if tools else None
        mode = _TOOL_CHOICE_MAP.get((tool_choice or "auto").strip().lower(), "AUTO")
        tool_config = None
        if gemini_tools:
            tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=mode)
            )
        response = self._generate(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=gemini_tools,
            tool_config=tool_config,
            disable_automatic_function_calling=True,
        )
        tool_calls = tuple(_parse_tool_calls(response))
        return LLMToolResponse(
            content=_extract_text(response) or None,
            tool_calls=tool_calls,
            model=_response_model(response, self._model),
            usage=_extract_usage(response),
            native_content=_model_content(response),
        )

    def _generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        max_tokens: int | None,
        temperature: float | None = None,
        tools: list[types.Tool] | None = None,
        tool_config: types.ToolConfig | None = None,
        response_mime_type: str | None = None,
        response_json_schema: dict[str, Any] | None = None,
        disable_automatic_function_calling: bool = False,
    ) -> Any:
        system_instruction, contents = _split_messages(messages)
        config_kwargs: dict[str, Any] = {
            "thinking_config": types.ThinkingConfig(thinking_level=self._thinking_level),
        }
        if max_tokens is not None:
            config_kwargs["max_output_tokens"] = max_tokens
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if tools:
            config_kwargs["tools"] = tools
        if tool_config is not None:
            config_kwargs["tool_config"] = tool_config
        if response_mime_type is not None:
            config_kwargs["response_mime_type"] = response_mime_type
        if response_json_schema is not None:
            config_kwargs["response_json_schema"] = response_json_schema
        if disable_automatic_function_calling:
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )

        try:
            return self._client.models.generate_content(
                model=self._model,
                contents=contents or [types.Content(role="user", parts=[types.Part(text="")])],
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"Gemini generateContent failed: {exc}") from exc


def tool_definition_to_function_declaration(tool: ToolDefinition) -> types.FunctionDeclaration:
    """Gemini-specific conversion from provider-agnostic ToolDefinition."""
    parameters = dict(tool.parameters or {})
    parameters.pop("$schema", None)
    parameters.pop("$defs", None)
    parameters.pop("definitions", None)
    if "type" not in parameters:
        parameters["type"] = "object"
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters_json_schema=parameters,
    )


def _to_gemini_tool(tool: ToolDefinition) -> types.Tool:
    return types.Tool(function_declarations=[tool_definition_to_function_declaration(tool)])


def _split_messages(
    messages: Sequence[LLMMessage],
) -> tuple[str | None, list[types.Content]]:
    system_parts: list[str] = []
    contents: list[types.Content] = []
    for message in messages:
        role = (message.role or "").strip().lower()
        if role == "system":
            if message.content:
                system_parts.append(message.content)
            continue
        contents.append(_to_gemini_content(message))
    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return system_instruction, contents


def _to_gemini_content(message: LLMMessage) -> types.Content:
    if message.native_content is not None:
        return message.native_content

    role = (message.role or "").strip().lower()
    if role in {"assistant", "model"}:
        parts: list[types.Part] = []
        if message.content:
            parts.append(types.Part(text=message.content))
        for call in message.tool_calls:
            parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        name=call.name,
                        args=call.arguments,
                        id=call.id or None,
                    )
                )
            )
        return types.Content(role="model", parts=parts or [types.Part(text="")])

    if role == "tool":
        payload: dict[str, Any]
        try:
            payload = json.loads(message.content or "{}")
        except json.JSONDecodeError:
            payload = {"result": message.content or ""}
        if not isinstance(payload, dict):
            payload = {"result": payload}
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=message.tool_call_id or None,
                        name=message.name or "",
                        response=payload,
                    )
                )
            ],
        )

    return types.Content(
        role="user",
        parts=[types.Part(text=message.content or "")],
    )


def _model_content(response: Any) -> Any | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    return getattr(candidates[0], "content", None)


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    parts: list[str] = []
    for part in _iter_parts(response):
        value = getattr(part, "text", None)
        if value:
            parts.append(str(value))
    return "".join(parts)


def _parse_tool_calls(response: Any) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for part in _iter_parts(response):
        function_call = getattr(part, "function_call", None)
        if function_call is None:
            continue
        name = str(getattr(function_call, "name", "") or "")
        raw_args = getattr(function_call, "args", None)
        if raw_args is None:
            arguments: dict[str, Any] = {}
        elif isinstance(raw_args, dict):
            arguments = dict(raw_args)
        else:
            try:
                arguments = dict(raw_args)
            except (TypeError, ValueError) as exc:
                raise LLMProviderError(
                    f"Gemini tool call arguments must be an object for tool '{name}'"
                ) from exc
        call_id = str(getattr(function_call, "id", "") or "")
        calls.append(ToolCall(id=call_id, name=name, arguments=arguments))
    return calls


def _iter_parts(response: Any) -> list[Any]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return []
    content = getattr(candidates[0], "content", None)
    return list(getattr(content, "parts", None) or [])


def _extract_usage(response: Any) -> LLMUsage | None:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    return LLMUsage(
        input_tokens=_as_optional_int(getattr(meta, "prompt_token_count", None)),
        output_tokens=_as_optional_int(getattr(meta, "candidates_token_count", None)),
        thinking_tokens=_as_optional_int(getattr(meta, "thoughts_token_count", None)),
        total_tokens=_as_optional_int(getattr(meta, "total_token_count", None)),
    )


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _response_model(response: Any, fallback: str) -> str:
    model = getattr(response, "model_version", None) or getattr(response, "model", None)
    return str(model) if model else fallback
