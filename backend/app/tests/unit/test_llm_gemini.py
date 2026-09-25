"""Unit tests for GeminiLLMProvider (mocked google-genai client)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.core.config.settings import AISettings
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.core.llm.base import LLMMessage, ToolDefinition
from app.ai.core.llm.gemini import (
    GeminiLLMProvider,
    tool_definition_to_function_declaration,
)
from app.ai.core.llm.mistral import MistralLLMProvider


def _usage_meta(
    *,
    prompt: int = 10,
    candidates: int = 4,
    thoughts: int = 2,
    total: int = 16,
):
    return SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        thoughts_token_count=thoughts,
        total_token_count=total,
    )


def _response(*, text: str | None = None, parts=None, usage=None, model="gemini-3.8-flash"):
    content = SimpleNamespace(parts=parts or [])
    candidate = SimpleNamespace(content=content)
    return SimpleNamespace(
        text=text,
        candidates=[candidate],
        usage_metadata=usage,
        model_version=model,
    )


def test_gemini_provider_requires_api_key_and_model():
    with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY"):
        GeminiLLMProvider(api_key="", model="gemini-3.8-flash")
    with pytest.raises(LLMConfigurationError, match="GEMINI_MODEL"):
        GeminiLLMProvider(api_key="key", model="")


def test_get_llm_provider_returns_gemini():
    settings = AISettings(
        ai_llm_provider="gemini",
        gemini_api_key="key",
        gemini_model="gemini-3.8-flash",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, GeminiLLMProvider)
    assert provider.thinking_level == "low"


def test_get_llm_provider_still_returns_mistral():
    settings = AISettings(
        ai_llm_provider="mistral",
        mistral_api_key="key",
        mistral_model="mistral-small-latest",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, MistralLLMProvider)


def test_tool_definition_conversion():
    tool = ToolDefinition(
        name="get_current_ai_context",
        description="Echo AI context",
        parameters={"type": "object", "properties": {}, "$schema": "http://json-schema.org/draft-07/schema#"},
    )
    declaration = tool_definition_to_function_declaration(tool)
    assert declaration.name == "get_current_ai_context"
    assert declaration.description == "Echo AI context"
    schema = declaration.parameters_json_schema
    assert schema["type"] == "object"
    assert "$schema" not in schema


def test_generate_text_normalizes_response_and_usage():
    client = MagicMock()
    client.models.generate_content.return_value = _response(
        text="hello",
        usage=_usage_meta(),
    )
    provider = GeminiLLMProvider(
        api_key="key",
        model="gemini-3.8-flash",
        client=client,
        thinking_level="low",
    )

    result = provider.generate_text([LLMMessage(role="user", content="Hi")])

    assert result.content == "hello"
    assert result.model == "gemini-3.8-flash"
    assert result.usage is not None
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 4
    assert result.usage.thinking_tokens == 2
    assert result.usage.total_tokens == 16

    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-3.8-flash"
    config = kwargs["config"]
    assert config.thinking_config is not None
    level = config.thinking_config.thinking_level
    assert str(level).lower().endswith("low") or getattr(level, "value", "").lower() == "low"
    assert config.max_output_tokens is None
    assert config.tools is None
    assert config.automatic_function_calling is not None
    assert config.automatic_function_calling.disable is True


def test_generate_text_forwards_temperature_and_max_tokens():
    client = MagicMock()
    client.models.generate_content.return_value = _response(text="ok")
    provider = GeminiLLMProvider(api_key="key", model="gemini-3.8-flash", client=client)
    provider.generate_text(
        [LLMMessage(role="user", content="Hi")],
        temperature=0.1,
        max_tokens=500,
    )
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.temperature == 0.1
    assert config.max_output_tokens == 500
    assert config.tools is None
    assert config.automatic_function_calling.disable is True


def test_generate_structured_disables_afc_and_passes_no_tools():
    client = MagicMock()
    client.models.generate_content.return_value = _response(
        text='{"answer": "ok"}',
        usage=_usage_meta(),
    )
    provider = GeminiLLMProvider(api_key="key", model="gemini-3.8-flash", client=client)
    result = provider.generate_structured(
        [LLMMessage(role="user", content="Q")],
        schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        temperature=0.1,
        max_tokens=500,
    )
    assert result.data == {"answer": "ok"}
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.tools is None
    assert config.tool_config is None
    assert config.response_mime_type == "application/json"
    assert config.automatic_function_calling is not None
    assert config.automatic_function_calling.disable is True
    assert config.temperature == 0.1
    assert config.max_output_tokens == 500


def test_generate_with_tools_parses_function_calls():
    client = MagicMock()
    function_call = SimpleNamespace(name="get_current_ai_context", args={}, id="call_1")
    part = SimpleNamespace(text=None, function_call=function_call)
    client.models.generate_content.return_value = _response(
        text=None,
        parts=[part],
        usage=_usage_meta(prompt=8, candidates=1, thoughts=1, total=10),
    )
    provider = GeminiLLMProvider(api_key="key", model="gemini-3.8-flash", client=client)

    result = provider.generate_with_tools(
        [LLMMessage(role="user", content="Call the tool")],
        [
            ToolDefinition(
                name="get_current_ai_context",
                description="context",
                parameters={"type": "object", "properties": {}},
            )
        ],
        tool_choice="any",
        max_tokens=512,
    )

    assert result.tool_calls[0].name == "get_current_ai_context"
    assert result.tool_calls[0].id == "call_1"
    assert result.tool_calls[0].arguments == {}
    assert result.native_content is not None
    assert result.usage is not None
    assert result.usage.thinking_tokens == 1

    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.max_output_tokens == 512
    assert config.tools
    assert config.tool_config is not None
    mode = config.tool_config.function_calling_config.mode
    assert str(mode).upper().endswith("ANY") or getattr(mode, "value", "") == "ANY"
    assert config.automatic_function_calling is not None
    assert config.automatic_function_calling.disable is True


def test_sdk_errors_are_wrapped():
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("quota")
    provider = GeminiLLMProvider(api_key="key", model="gemini-3.8-flash", client=client)
    with pytest.raises(LLMProviderError, match="Gemini generateContent failed"):
        provider.generate_text([LLMMessage(role="user", content="Hi")])
