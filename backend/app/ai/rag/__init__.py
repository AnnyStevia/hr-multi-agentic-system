"""RAG package — foundation scaffold (Phase 5.1).

Do not import models here; importing Vector-backed models would register them
on Base.metadata and break SQLite unit-test create_all.
"""

from app.ai.rag.config import RAGSettings, rag_settings

__all__ = ["RAGSettings", "rag_settings"]
