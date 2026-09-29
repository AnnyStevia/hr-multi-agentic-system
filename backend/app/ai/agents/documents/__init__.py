"""Documents Agent — read-only metadata + Document Understanding tools."""

from __future__ import annotations

from app.ai.agents.documents.agent import DocumentsAgent
from app.ai.agents.documents.exceptions import (
    DocumentsAgentAuthorizationError,
    DocumentsAgentError,
    DocumentsAgentValidationError,
)
from app.ai.agents.documents.schemas import (
    DOCUMENTS_AGENT_ID,
    DocumentsAgentAnswer,
    DocumentsAgentDocumentAnswer,
    DocumentsAgentDocumentSummary,
    DocumentsAgentRequest,
    DocumentsAgentUsage,
)
from app.ai.agents.documents.service import build_documents_agent

__all__ = [
    "DOCUMENTS_AGENT_ID",
    "DocumentsAgent",
    "DocumentsAgentAnswer",
    "DocumentsAgentAuthorizationError",
    "DocumentsAgentDocumentAnswer",
    "DocumentsAgentDocumentSummary",
    "DocumentsAgentError",
    "DocumentsAgentRequest",
    "DocumentsAgentUsage",
    "DocumentsAgentValidationError",
    "build_documents_agent",
]
