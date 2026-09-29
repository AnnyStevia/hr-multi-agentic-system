"""Document Agent request/response schemas (read-only)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext

DOCUMENTS_AGENT_ID = "documents"


class DocumentsAgentUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class DocumentsAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    question: str = Field(min_length=1, max_length=4000)
    context: AIExecutionContext


class DocumentsAgentDocumentSummary(BaseModel):
    """Structured summary from summarize_document (for Document AI UX)."""

    model_config = ConfigDict(extra="forbid")

    title: str = ""
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    important_dates: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    document_id: int | None = None
    document_type: str | None = None
    truncated: bool = False


class DocumentsAgentDocumentCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int
    excerpt: str | None = None


class DocumentsAgentDocumentAnswer(BaseModel):
    """Structured Q&A from ask_about_document (for Document AI UX)."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[DocumentsAgentDocumentCitation] = Field(default_factory=list)
    document_id: int | None = None
    document_type: str | None = None
    truncated: bool = False


class DocumentsAgentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    agent_id: str = DOCUMENTS_AGENT_ID
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: DocumentsAgentUsage | None = None
    pending_confirmation: None = None
    document_summary: DocumentsAgentDocumentSummary | None = None
    document_answer: DocumentsAgentDocumentAnswer | None = None
