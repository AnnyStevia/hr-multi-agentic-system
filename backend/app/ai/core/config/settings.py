from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Environment-backed settings for the AI layer only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ai_llm_provider: str = "gemini"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # When true and the deterministic router returns clarify, ask LLMProvider to
    # pick among available agent ids only. Default false preserves router parity.
    ai_orchestrator_llm_clarify: bool = False


ai_settings = AISettings()
