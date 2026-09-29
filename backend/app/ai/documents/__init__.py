"""Document Understanding foundation (Phase 11.2A) — service layer only."""

from app.ai.documents.access import AuthorizedDocumentAccess
from app.ai.documents.exceptions import (
    DocumentUnderstandingAuthorizationError,
    DocumentUnderstandingError,
    DocumentUnderstandingLLMError,
    DocumentUnderstandingNotFoundError,
    DocumentUnderstandingParseError,
    DocumentUnderstandingUnsupportedError,
    DocumentUnderstandingValidationError,
)
from app.ai.documents.prompts import DOCUMENT_ABSTENTION
from app.ai.documents.schemas import (
    DocumentAnswer,
    DocumentCitation,
    DocumentContentContext,
    DocumentRef,
    DocumentSourceType,
    DocumentSummary,
)
from app.ai.documents.service import DocumentUnderstandingService

__all__ = [
    "AuthorizedDocumentAccess",
    "DOCUMENT_ABSTENTION",
    "DocumentAnswer",
    "DocumentCitation",
    "DocumentContentContext",
    "DocumentRef",
    "DocumentSourceType",
    "DocumentSummary",
    "DocumentUnderstandingAuthorizationError",
    "DocumentUnderstandingError",
    "DocumentUnderstandingLLMError",
    "DocumentUnderstandingNotFoundError",
    "DocumentUnderstandingParseError",
    "DocumentUnderstandingService",
    "DocumentUnderstandingUnsupportedError",
    "DocumentUnderstandingValidationError",
]
