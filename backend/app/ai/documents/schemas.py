"""Schemas for Document Understanding (Phase 11.2A)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DocumentSourceType(str, Enum):
    COMPANY = "company"
    EMPLOYEE = "employee"
    PRIVATE = "private"
    # Explicitly unsupported in this phase (Recruitment owns CVs).
    APPLICATION = "application"


class DocumentRef(BaseModel):
    """Caller-selected document identity (no storage keys)."""

    source_type: DocumentSourceType
    document_id: int = Field(..., ge=1)
    # Required when HR/Admin loads another employee's document.
    employee_id: int | None = Field(default=None, ge=1)


class DocumentPage(BaseModel):
    page_number: int = Field(..., ge=1)
    text: str


class DocumentContentContext(BaseModel):
    """Authorized, parsed document content for LLM prompts (DATA only)."""

    document_id: int
    source_type: DocumentSourceType
    title: str | None = None
    filename: str
    content_type: str
    page_count: int
    pages: list[DocumentPage]
    truncated: bool = False
    character_count: int = 0


class DocumentSummary(BaseModel):
    title: str = ""
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    important_dates: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    document_id: int | None = None
    source_type: DocumentSourceType | None = None
    truncated: bool = False
    model: str = ""


class DocumentCitation(BaseModel):
    page_number: int = Field(..., ge=1)
    excerpt: str | None = None


class DocumentAnswer(BaseModel):
    answer: str
    citations: list[DocumentCitation] = Field(default_factory=list)
    document_id: int | None = None
    source_type: DocumentSourceType | None = None
    truncated: bool = False
    has_context: bool = True
    model: str = ""


SUMMARY_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "important_dates": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "summary",
        "key_points",
        "important_dates",
        "action_items",
    ],
}

ANSWER_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "excerpt": {"type": "string"},
                },
                "required": ["page_number"],
            },
        },
    },
    "required": ["answer", "citations"],
}
