"""Structured results for document ingestion (no chunking / provenance yet)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestedPage(BaseModel):
    model_config = {"extra": "forbid"}

    page_number: int = Field(ge=1)
    text: str


class IngestionResult(BaseModel):
    model_config = {"extra": "forbid"}

    company_document_id: int
    filename: str
    content_type: str
    total_pages: int = Field(ge=0)
    extracted_text: str
    pages: list[IngestedPage] = Field(default_factory=list)
