"""Document Understanding settings (Phase 11.2A — no secrets)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentUnderstandingSettings(BaseSettings):
    """Limits for single-document summarize / Q&A (not Company RAG)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    doc_understanding_max_pages: int = 40
    doc_understanding_max_characters: int = 30_000
    doc_understanding_max_output_tokens: int = 800
    doc_understanding_temperature: float = 0.1
    doc_understanding_max_excerpt_chars: int = 240


document_understanding_settings = DocumentUnderstandingSettings()
