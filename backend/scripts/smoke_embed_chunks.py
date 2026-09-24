"""Smoke: embed existing KnowledgeChunks via Gemini Embedding 2 (ONE live call set).

Run from backend/ after Phase 5.3 chunks exist for DOCUMENT_ID:

  $env:PYTHONPATH = "."
  python scripts/smoke_embed_chunks.py

Uses GEMINI_API_KEY. Does not call the conversational Gemini model.
"""

from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.ai.rag import models as rag_models  # noqa: F401

from app.ai.rag.chunking import KnowledgeChunkRepository, KnowledgeChunkService
from app.ai.rag.config import rag_settings
from app.ai.rag.embeddings import EmbeddingService, get_embedding_provider
from app.ai.rag.ingestion import DocumentIngestionService
from app.core.database import SessionLocal
from app.modules.documents.library_repository import CompanyDocumentRepository
from app.shared.storage import get_storage_service

DOCUMENT_ID = 2  # existing small one-page company PDF

db = SessionLocal()
try:
    doc = CompanyDocumentRepository(db).get_by_id(DOCUMENT_ID)
    assert doc is not None, "document not found"
    print("document_id:", doc.id)
    print("document_version:", doc.version)

    repo = KnowledgeChunkRepository(db)
    chunks = repo.list_by_company_document_id(DOCUMENT_ID)
    if not chunks:
        print("no chunks found — ingesting+chunking once")
        storage = get_storage_service()
        ingestion = DocumentIngestionService(storage).ingest_company_document(doc)
        chunks = KnowledgeChunkService(db, storage).replace_chunks_from_ingestion(
            doc, ingestion
        )

    print("chunk_count:", len(chunks))
    print("embedding_model:", rag_settings.rag_embedding_model)
    print("embedding_dimensions:", rag_settings.rag_embedding_dimensions)

    provider = get_embedding_provider()
    result = EmbeddingService(db, provider).embed_company_document_chunks(DOCUMENT_ID)

    print("embedded_count:", result.embedded_count)
    print("skipped_count:", result.skipped_count)
    if result.usage_input_tokens is not None:
        print("usage_input_tokens:", result.usage_input_tokens)
    if result.usage_total_tokens is not None:
        print("usage_total_tokens:", result.usage_total_tokens)

    refreshed = repo.list_by_company_document_id(DOCUMENT_ID)
    assert refreshed, "expected at least one chunk"
    first = refreshed[0]
    assert first.embedding is not None, "embedding IS NULL"
    vector = list(first.embedding)
    assert len(vector) == rag_settings.rag_embedding_dimensions
    assert first.embedding_model == rag_settings.rag_embedding_model
    assert first.embedding_dimensions == rag_settings.rag_embedding_dimensions

    preview = ", ".join(f"{v:.6f}" for v in vector[:5])
    print("first_vector_values:", f"[{preview}, …]")
    print("vector_length:", len(vector))
    print("db_embedding_model:", first.embedding_model)
    print("db_embedding_dimensions:", first.embedding_dimensions)
    print("smoke_embed_ok: True")
finally:
    db.close()
