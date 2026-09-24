from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.core.config.settings import AISettings
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.core.llm.base import LLMMessage, ToolDefinition
from app.ai.core.llm.mistral import MistralLLMProvider


def _choice(*, content=None, tool_calls=None, model: str = "mistral-small-latest"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], model=model)


def test_generate_text_returns_assistant_content():
    client = MagicMock()
    client.chat.complete.return_value = _choice(content="Hello from Mistral")
    provider = MistralLLMProvider(
        api_key="test-key",
        model="mistral-small-latest",
        client=client,
    )

    result = provider.generate_text(
        [LLMMessage(role="user", content="Hi")],
        temperature=0.2,
        max_tokens=64,
    )

    assert result.content == "Hello from Mistral"
    assert result.model == "mistral-small-latest"
    kwargs = client.chat.complete.call_args.kwargs
    assert kwargs["model"] == "mistral-small-latest"
    assert kwargs["messages"] == [{"role": "user", "content": "Hi"}]
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 64


def test_generate_structured_parses_json_object():
    client = MagicMock()
    client.chat.complete.return_value = _choice(content='{"status":"ok","count":2}')
    provider = MistralLLMProvider(
        api_key="test-key",
        model="mistral-small-latest",
        client=client,
    )
    schema = {
        "title": "StatusPayload",
        "type": "object",
        "properties": {"status": {"type": "string"}, "count": {"type": "integer"}},
    }

    result = provider.generate_structured(
        [LLMMessage(role="user", content="Summarize")],
        schema=schema,
    )

    assert result.data == {"status": "ok", "count": 2}
    response_format = client.chat.complete.call_args.kwargs["response_format"]
    assert response_format.type == "json_schema"
    assert response_format.json_schema.name == "StatusPayload"


def test_generate_with_tools_parses_tool_calls():
    client = MagicMock()
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="lookup_employee", arguments='{"employee_id": 7}'),
    )
    client.chat.complete.return_value = _choice(content=None, tool_calls=[tool_call])
    provider = MistralLLMProvider(
        api_key="test-key",
        model="mistral-small-latest",
        client=client,
    )
    tools = [
        ToolDefinition(
            name="lookup_employee",
            description="Find an employee by id",
            parameters={
                "type": "object",
                "properties": {"employee_id": {"type": "integer"}},
            },
        )
    ]

    result = provider.generate_with_tools(
        [LLMMessage(role="user", content="Who is employee 7?")],
        tools,
        tool_choice="auto",
    )

    assert result.content is None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_1"
    assert result.tool_calls[0].name == "lookup_employee"
    assert result.tool_calls[0].arguments == {"employee_id": 7}
    kwargs = client.chat.complete.call_args.kwargs
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["tools"][0].function.name == "lookup_employee"


def test_mistral_provider_requires_api_key_and_model():
    with pytest.raises(LLMConfigurationError, match="MISTRAL_API_KEY"):
        MistralLLMProvider(api_key="", model="mistral-small-latest")
    with pytest.raises(LLMConfigurationError, match="MISTRAL_MODEL"):
        MistralLLMProvider(api_key="key", model="")


def test_get_llm_provider_rejects_unknown_provider():
    settings = AISettings(
        ai_llm_provider="openai",
        mistral_api_key="key",
        mistral_model="mistral-small-latest",
    )
    with pytest.raises(LLMConfigurationError, match="Unsupported AI_LLM_PROVIDER"):
        get_llm_provider(settings)


def test_get_llm_provider_returns_mistral():
    settings = AISettings(
        ai_llm_provider="mistral",
        mistral_api_key="key",
        mistral_model="mistral-small-latest",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, MistralLLMProvider)


def test_sdk_errors_are_wrapped():
    client = MagicMock()
    client.chat.complete.side_effect = RuntimeError("network down")
    provider = MistralLLMProvider(
        api_key="test-key",
        model="mistral-small-latest",
        client=client,
    )
    with pytest.raises(LLMProviderError, match="Mistral chat completion failed"):
        provider.generate_text([LLMMessage(role="user", content="Hi")])
