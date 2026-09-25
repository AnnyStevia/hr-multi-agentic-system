"""Schemas for the Knowledge Agent (orchestrates existing RAG services)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.ai.core.context.models import AIExecutionContext


class KnowledgeAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    question: str
    context: AIExecutionContext
    top_k: int | None = None
