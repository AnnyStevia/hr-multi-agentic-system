"""Offboarding Agent exceptions."""

from app.ai.core.exceptions import AIException


class OffboardingAgentError(AIException):
    """Controlled Offboarding Agent failure."""


class OffboardingAgentValidationError(OffboardingAgentError):
    """Invalid Offboarding Agent request."""


class OffboardingAgentAuthorizationError(OffboardingAgentError):
    """Caller is not authorized for the requested offboarding action."""
