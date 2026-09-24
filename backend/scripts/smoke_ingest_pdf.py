"""Smoke: CompanyDocument → S3 → PDF ingest → chunk persist (no embeddings).

Run from backend/:
  $env:PYTHONPATH = "."
  python scripts/smoke_ingest_pdf.py
"""

# Import models so SQLAlchemy can resolve relationships (Employee, User, …).
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.ai.rag import models as rag_models  # noqa: F401

from app.ai.rag.chunking import KnowledgeChunkService
from app.ai.rag.ingestion import DocumentIngestionService
from app.core.database import SessionLocal
from app.modules.documents.library_repository import CompanyDocumentRepository
from app.shared.storage import get_storage_service

DOCUMENT_ID = 2  # company document id

db = SessionLocal()
try:
    doc = CompanyDocumentRepository(db).get_by_id(DOCUMENT_ID)
    assert doc is not None, "document not found"
    print("storage_key:", doc.storage_key)
    print("content_type:", doc.content_type)
    print("document_version:", doc.version)

    storage = get_storage_service()
    raw = storage.download_file(doc.storage_key)
    print("downloaded_bytes:", len(raw))

    ingestion = DocumentIngestionService(storage).ingest_company_document(doc)
    print("total_pages:", ingestion.total_pages)
    for p in ingestion.pages:
        preview = (p.text[:80] + "…") if len(p.text) > 80 else p.text
        print(f"page {p.page_number}: {preview!r}")
    print("extracted_text_len:", len(ingestion.extracted_text))

    chunks = KnowledgeChunkService(db, storage).replace_chunks_from_ingestion(
        doc, ingestion
    )
    print("chunk_count:", len(chunks))
    for chunk in chunks:
        assert chunk.embedding is None
        assert chunk.content.strip()
        print(
            f"chunk {chunk.chunk_index}: pages {chunk.page_start}-{chunk.page_end} "
            f"hash={chunk.content_hash[:12]}… words={len(chunk.content.split())}"
        )
    if chunks:
        print("first_content_hash:", chunks[0].content_hash)
    print("embeddings_all_null:", all(c.embedding is None for c in chunks))
finally:
    db.close()
