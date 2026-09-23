from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Environment-backed settings for the AI layer only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ai_llm_provider: str = "mistral"
    mistral_api_key: str = ""
    mistral_model: str = ""


ai_settings = AISettings()
