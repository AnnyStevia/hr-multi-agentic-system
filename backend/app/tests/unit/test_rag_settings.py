"""Unit tests for RAGSettings (no Gemini / no DB)."""

from app.ai.rag.config import RAGSettings, rag_settings


def test_rag_settings_defaults():
    settings = RAGSettings(
        rag_embedding_model="gemini-embedding-2",
        rag_embedding_dimensions=768,
        rag_vector_distance="cosine",
        rag_chunk_size=800,
        rag_chunk_overlap=100,
        rag_embed_max_batch_size=32,
        rag_retrieval_top_k=5,
        rag_retrieval_max_top_k=20,
        rag_retrieval_min_similarity=None,
        rag_rrf_k=60,
        rag_hybrid_vector_candidates=20,
        rag_hybrid_fts_candidates=20,
        rag_hybrid_max_candidates=50,
        rag_query_max_characters=1000,
        rag_context_max_chunks=5,
        rag_context_max_characters=12000,
        rag_generation_max_output_tokens=500,
        rag_generation_temperature=0.1,
    )
    assert settings.rag_generation_max_output_tokens == 500
    assert settings.rag_generation_temperature == 0.1
    assert rag_settings.rag_embedding_dimensions == 768


def test_rag_settings_env_override(monkeypatch):
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "custom-embed")
    monkeypatch.setenv("RAG_EMBEDDING_DIMENSIONS", "1536")
    monkeypatch.setenv("RAG_VECTOR_DISTANCE", "l2")
    monkeypatch.setenv("RAG_CHUNK_SIZE", "400")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "50")
    monkeypatch.setenv("RAG_EMBED_MAX_BATCH_SIZE", "8")
    monkeypatch.setenv("RAG_RETRIEVAL_TOP_K", "3")
    monkeypatch.setenv("RAG_RETRIEVAL_MAX_TOP_K", "10")
    monkeypatch.setenv("RAG_RETRIEVAL_MIN_SIMILARITY", "0.25")
    monkeypatch.setenv("RAG_RRF_K", "40")
    monkeypatch.setenv("RAG_HYBRID_VECTOR_CANDIDATES", "15")
    monkeypatch.setenv("RAG_HYBRID_FTS_CANDIDATES", "12")
    monkeypatch.setenv("RAG_HYBRID_MAX_CANDIDATES", "30")
    monkeypatch.setenv("RAG_QUERY_MAX_CHARACTERS", "200")
    monkeypatch.setenv("RAG_CONTEXT_MAX_CHUNKS", "3")
    monkeypatch.setenv("RAG_CONTEXT_MAX_CHARACTERS", "5000")
    monkeypatch.setenv("RAG_GENERATION_MAX_OUTPUT_TOKENS", "250")
    monkeypatch.setenv("RAG_GENERATION_TEMPERATURE", "0.05")
    settings = RAGSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.rag_generation_max_output_tokens == 250
    assert settings.rag_generation_temperature == 0.05
