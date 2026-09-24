"""RAG-layer exceptions (AI package only)."""

from app.ai.core.exceptions import AIException


class RAGException(AIException):
    """Base error for the RAG layer."""


class UnsupportedDocumentError(RAGException):
    """Raised when a document kind or format is not eligible for ingestion."""


class DocumentParseError(RAGException):
    """Raised when document bytes cannot be parsed into text."""


class DocumentIngestionError(RAGException):
    """Raised when ingestion fails (e.g. storage/key issues)."""
