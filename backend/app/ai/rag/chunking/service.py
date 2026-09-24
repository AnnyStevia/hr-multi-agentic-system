"""Turn Phase 5.2 ingestion results into KnowledgeChunk rows (no embeddings)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.rag.chunking.chunker import DocumentChunker
from app.ai.rag.chunking.repository import KnowledgeChunkRepository
from app.ai.rag.chunking.schemas import ChunkDraft
from app.ai.rag.exceptions import UnsupportedDocumentError
from app.ai.rag.ingestion.schemas import IngestionResult
from app.ai.rag.ingestion.service import DocumentIngestionService
from app.ai.rag.models import KnowledgeChunk
from app.modules.documents.models import CompanyDocument
from app.shared.storage.base import StorageService


class KnowledgeChunkService:
    """Chunk and persist company-library documents transactionally."""

    def __init__(
        self,
        db: Session,
        storage: StorageService | None = None,
        *,
        ingestion_service: DocumentIngestionService | None = None,
        chunker: DocumentChunker | None = None,
        repository: KnowledgeChunkRepository | None = None,
    ) -> None:
        self.db = db
        self._repository = repository or KnowledgeChunkRepository(db)
        self._chunker = chunker or DocumentChunker()
        if ingestion_service is not None:
            self._ingestion = ingestion_service
        elif storage is not None:
            self._ingestion = DocumentIngestionService(storage)
        else:
            self._ingestion = None

    def replace_chunks_from_ingestion(
        self,
        document: CompanyDocument,
        ingestion: IngestionResult,
    ) -> list[KnowledgeChunk]:
        self._require_company_document(document)
        drafts = self._chunker.chunk(ingestion, document_version=document.version)
        return self._replace_chunks(document.id, drafts)

    def ingest_and_replace_chunks(self, document: CompanyDocument) -> list[KnowledgeChunk]:
        self._require_company_document(document)
        if self._ingestion is None:
            raise RuntimeError(
                "KnowledgeChunkService requires storage or ingestion_service "
                "to ingest documents"
            )
        ingestion = self._ingestion.ingest_company_document(document)
        return self.replace_chunks_from_ingestion(document, ingestion)

    def _replace_chunks(
        self,
        company_document_id: int,
        drafts: list[ChunkDraft],
    ) -> list[KnowledgeChunk]:
        try:
            self._repository.delete_by_company_document_id(company_document_id)
            rows = [
                KnowledgeChunk(
                    company_document_id=company_document_id,
                    content=draft.content,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    chunk_index=draft.chunk_index,
                    content_hash=draft.content_hash,
                    chunk_metadata=dict(draft.metadata),
                    embedding=None,
                    embedding_model=None,
                    embedding_dimensions=None,
                )
                for draft in drafts
            ]
            if rows:
                self._repository.add_many(rows)
            self.db.commit()
            return rows
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _require_company_document(document: object) -> None:
        if not isinstance(document, CompanyDocument):
            raise UnsupportedDocumentError(
                "Only Company Document Library documents can be chunked"
            )
