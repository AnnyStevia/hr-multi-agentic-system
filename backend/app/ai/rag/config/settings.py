from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    """Environment-backed settings for the RAG layer only (no secrets).

    Chunk size/overlap are whitespace-separated word counts (deterministic
    approximation; no tokenizer dependency).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    rag_embedding_model: str = "gemini-embedding-2"
    rag_embedding_dimensions: int = 768
    rag_vector_distance: str = "cosine"
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100


rag_settings = RAGSettings()
