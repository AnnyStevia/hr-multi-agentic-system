"""Phase 5.3 deterministic chunking, provenance, and KnowledgeChunk persistence."""

from app.ai.rag.chunking.chunker import DocumentChunker
from app.ai.rag.chunking.hasher import sha256_hex
from app.ai.rag.chunking.repository import KnowledgeChunkRepository
from app.ai.rag.chunking.schemas import ChunkDraft
from app.ai.rag.chunking.service import KnowledgeChunkService

__all__ = [
    "ChunkDraft",
    "DocumentChunker",
    "KnowledgeChunkRepository",
    "KnowledgeChunkService",
    "sha256_hex",
]
