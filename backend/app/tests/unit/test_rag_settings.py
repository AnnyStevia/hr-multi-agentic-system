"""Unit tests for RAGSettings (no Gemini / no DB)."""

from app.ai.rag.config import RAGSettings, rag_settings


def test_rag_settings_defaults():
    settings = RAGSettings(
        rag_embedding_model="gemini-embedding-2",
        rag_embedding_dimensions=768,
        rag_vector_distance="cosine",
        rag_chunk_size=800,
        rag_chunk_overlap=100,
    )
    assert settings.rag_embedding_model == "gemini-embedding-2"
    assert settings.rag_embedding_dimensions == 768
    assert settings.rag_vector_distance == "cosine"
    assert settings.rag_chunk_size == 800
    assert settings.rag_chunk_overlap == 100
    assert rag_settings.rag_embedding_dimensions == 768


def test_rag_settings_env_override(monkeypatch):
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "custom-embed")
    monkeypatch.setenv("RAG_EMBEDDING_DIMENSIONS", "1536")
    monkeypatch.setenv("RAG_VECTOR_DISTANCE", "l2")
    monkeypatch.setenv("RAG_CHUNK_SIZE", "400")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "50")
    settings = RAGSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.rag_embedding_model == "custom-embed"
    assert settings.rag_embedding_dimensions == 1536
    assert settings.rag_vector_distance == "l2"
    assert settings.rag_chunk_size == 400
    assert settings.rag_chunk_overlap == 50
