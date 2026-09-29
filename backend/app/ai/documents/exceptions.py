"""Document Understanding exceptions (AI package only)."""

from app.ai.core.exceptions import AIException


class DocumentUnderstandingError(AIException):
    """Base error for document understanding."""


class DocumentUnderstandingAuthorizationError(DocumentUnderstandingError):
    """Caller is not allowed to access the requested document."""


class DocumentUnderstandingNotFoundError(DocumentUnderstandingError):
    """Document missing or intentionally opaque (same messaging as Core HR)."""


class DocumentUnderstandingUnsupportedError(DocumentUnderstandingError):
    """Unsupported source type or content type for this feature."""


class DocumentUnderstandingParseError(DocumentUnderstandingError):
    """PDF parse / extraction failure."""


class DocumentUnderstandingValidationError(DocumentUnderstandingError):
    """Invalid input or model output that cannot be used safely."""


class DocumentUnderstandingLLMError(DocumentUnderstandingError):
    """LLM provider failure during understanding."""
