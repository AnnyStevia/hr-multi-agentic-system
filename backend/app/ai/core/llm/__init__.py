from app.ai.core.config import ai_settings
from app.ai.core.exceptions import LLMConfigurationError
from app.ai.core.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMStructuredResponse,
    LLMTextResponse,
    LLMToolResponse,
    ToolCall,
    ToolDefinition,
)
from app.ai.core.llm.mistral import MistralLLMProvider

__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMStructuredResponse",
    "LLMTextResponse",
    "LLMToolResponse",
    "MistralLLMProvider",
    "ToolCall",
    "ToolDefinition",
    "get_llm_provider",
]


def get_llm_provider(settings=None) -> LLMProvider:
    """Return the configured LLM provider implementation."""
    cfg = settings if settings is not None else ai_settings
    provider = (cfg.ai_llm_provider or "").strip().lower()
    if provider == "mistral":
        return MistralLLMProvider(
            api_key=cfg.mistral_api_key,
            model=cfg.mistral_model,
        )
    if not provider:
        raise LLMConfigurationError("AI_LLM_PROVIDER is required")
    raise LLMConfigurationError(f"Unsupported AI_LLM_PROVIDER: {provider}")
