"""Repository for KnowledgeChunk persistence (Phase 5.3)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.rag.models import KnowledgeChunk


class KnowledgeChunkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def delete_by_company_document_id(self, company_document_id: int) -> int:
        deleted = (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.company_document_id == company_document_id)
            .delete(synchronize_session=False)
        )
        return int(deleted or 0)

    def add_many(self, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        for chunk in chunks:
            self.db.add(chunk)
        self.db.flush()
        return chunks

    def list_by_company_document_id(
        self, company_document_id: int
    ) -> list[KnowledgeChunk]:
        return (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.company_document_id == company_document_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
            .all()
        )

    def get_by_id(self, chunk_id: int) -> KnowledgeChunk | None:
        return (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.id == chunk_id)
            .first()
        )

    def save_embeddings(self, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        """Flush embedding column updates for the given chunks."""
        for chunk in chunks:
            self.db.add(chunk)
        self.db.flush()
        return chunks
