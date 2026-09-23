"""AI-layer exceptions (decoupled from Core HR AppException)."""


class AIException(Exception):
    """Base error for the AI layer."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class LLMConfigurationError(AIException):
    """Raised when LLM provider settings are missing or invalid."""


class LLMProviderError(AIException):
    """Raised when an LLM provider call fails."""
