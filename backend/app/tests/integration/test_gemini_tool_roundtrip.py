"""Live Gemini tool-roundtrip smoke test (skipped without API credentials)."""

import pytest

from app.ai.core.config import ai_settings
from app.ai.core.context import AIExecutionContext
from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.core.config.settings import AISettings
from app.ai.orchestration import run_controlled_gemini_smoke
from app.ai.tools import GetCurrentAiContextTool, ToolRegistry

_HAS_GEMINI = bool(ai_settings.gemini_api_key.strip())

pytestmark = pytest.mark.skipif(
    not _HAS_GEMINI,
    reason="GEMINI_API_KEY not configured",
)

# Intro pricing for gemini-3.8-flash through 2026-12-31 (USD per 1M tokens).
_INPUT_USD_PER_M = 0.75
_OUTPUT_USD_PER_M = 3.75  # includes thinking tokens


def _authorized_context() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=101,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=55,
        candidate_id=None,
    )


def _approx_cost_usd(usage) -> float | None:
    if usage is None:
        return None
    input_tokens = usage.input_tokens or 0
    output_tokens = (usage.output_tokens or 0) + (usage.thinking_tokens or 0)
    return (input_tokens / 1_000_000) * _INPUT_USD_PER_M + (
        output_tokens / 1_000_000
    ) * _OUTPUT_USD_PER_M


def test_live_gemini_controlled_smoke():
    settings = AISettings(
        ai_llm_provider="gemini",
        gemini_api_key=ai_settings.gemini_api_key,
        gemini_model=ai_settings.gemini_model or "gemini-3.8-flash",
    )
    provider = get_llm_provider(settings)
    registry = ToolRegistry()
    registry.register(GetCurrentAiContextTool())

    try:
        result = run_controlled_gemini_smoke(
            provider=provider,
            context=_authorized_context(),
            registry=registry,
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if any(
            token in message
            for token in (
                "429",
                "rate",
                "quota",
                "resource_exhausted",
                "billing",
                "insufficient",
            )
        ):
            pytest.skip(f"Gemini rate/quota/billing issue: {exc}")
        raise

    assert result.tool_names_called == ("get_current_ai_context",)
    assert len(result.tool_results) == 1
    data = result.tool_results[0].data
    assert data is not None
    assert data["user_id"] == 101
    assert data["roles"] == ["employee"]
    assert data["employee_id"] == 55
    assert result.final_content.strip()
    assert result.model.strip()

    usage = result.usage
    cost = _approx_cost_usd(usage)
    print(f"Gemini model used: {result.model}")
    print("Thinking level: low")
    if usage is not None:
        print(
            "Token usage:"
            f" input={usage.input_tokens}"
            f" output={usage.output_tokens}"
            f" thinking={usage.thinking_tokens}"
            f" total={usage.total_tokens}"
        )
    print(f"Approximate cost USD: {cost}")
    print(f"Final response: {result.final_content[:240]}")
