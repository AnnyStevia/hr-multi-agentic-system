from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    """Environment-backed settings for the RAG layer only (no secrets).

    Chunk size/overlap are whitespace-separated word counts (deterministic
    approximation; no tokenizer dependency).

    rag_embed_max_batch_size caps how many pending chunk texts are passed to
    the provider in one service pass. For gemini-embedding-2 the provider still
    issues one embed_content call per text (model aggregates multi-string input).

    Vector retrieval uses cosine distance in PostgreSQL/pgvector.
    Hybrid retrieval (Phase 5.6) fuses vector + FTS ranks with RRF.
    RAG query pipeline (Phase 5.7) embeds the user query then assembles context.
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
    rag_embed_max_batch_size: int = 32
    rag_retrieval_top_k: int = 5
    rag_retrieval_max_top_k: int = 20
    rag_retrieval_min_similarity: float | None = None
    rag_rrf_k: int = 60
    rag_hybrid_vector_candidates: int = 20
    rag_hybrid_fts_candidates: int = 20
    rag_hybrid_max_candidates: int = 50
    rag_query_max_characters: int = 1000
    rag_context_max_chunks: int = 5
    rag_context_max_characters: int = 12000


rag_settings = RAGSettings()
