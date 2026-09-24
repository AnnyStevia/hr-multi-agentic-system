"""Live Mistral tool-roundtrip smoke test (skipped without API credentials)."""

import pytest

from app.ai.core.config import ai_settings
from app.ai.core.context import AIExecutionContext
from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.orchestration import run_tool_roundtrip
from app.ai.tools import GetCurrentAiContextTool, ToolRegistry

_HAS_MISTRAL = bool(ai_settings.mistral_api_key.strip())

pytestmark = pytest.mark.skipif(
    not _HAS_MISTRAL,
    reason="MISTRAL_API_KEY not configured",
)


def _authorized_context() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=101,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=55,
        candidate_id=None,
    )


def test_live_mistral_tool_roundtrip_authenticated():
    registry = ToolRegistry()
    registry.register(GetCurrentAiContextTool())
    provider = get_llm_provider()

    try:
        result = run_tool_roundtrip(
            provider=provider,
            context=_authorized_context(),
            registry=registry,
            user_prompt=(
                "Please call the get_current_ai_context tool and briefly summarize "
                "my user_id and roles from the tool result."
            ),
            tool_choice="any",
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if "429" in message or "rate_limited" in message or "rate limit" in message:
            pytest.skip(f"Mistral rate limited (retry later): {exc}")
        raise

    assert result.tool_names_called == ("get_current_ai_context",)
    assert len(result.tool_results) == 1
    data = result.tool_results[0].data
    assert data is not None
    assert data["user_id"] == 101
    assert data["roles"] == ["employee"]
    assert data["employee_id"] == 55
    assert data["candidate_id"] is None
    assert result.final_content.strip()
    assert result.model.strip()
    # Surface model for manual report when running with -s
    print(f"Mistral model used: {result.model}")
    print(f"Final response: {result.final_content[:240]}")
