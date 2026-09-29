"""Smoke: Document Agent read-only tools (mocked LLM + services by default).

Run from backend/:

  $env:PYTHONPATH = "."
  .\\.venv\\Scripts\\python.exe scripts/smoke_document_agent.py

Does not upload, archive, delete, or call live Gemini by default.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.ai.agents.documents import DocumentsAgentRequest, build_documents_agent
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm.base import LLMStructuredResponse, LLMTextResponse, LLMToolResponse, ToolCall
from app.ai.documents import DocumentAnswer, DocumentSourceType, DocumentSummary
from app.ai.documents.schemas import DocumentCitation
from app.modules.documents.models import (
    CompanyDocumentRagIndexStatus,
    CompanyDocumentStatus,
)


def _company_doc():
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=42,
        title="Employee Handbook",
        description="Company handbook",
        category_id=1,
        category=SimpleNamespace(slug="handbook", label="Handbook"),
        original_filename="handbook.pdf",
        content_type="application/pdf",
        size_bytes=100,
        version=1,
        uploaded_by_user_id=1,
        uploaded_by=SimpleNamespace(first_name="A", last_name="B"),
        status=CompanyDocumentStatus.ACTIVE,
        rag_index_status=CompanyDocumentRagIndexStatus.READY,
        rag_indexed_at=now,
        rag_indexing_error=None,
        created_at=now,
        updated_at=now,
    )


class _ScriptedLLM:
    """Forces list+get+summarize+ask in one tool round, then final answer."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_with_tools(self, messages, tools, **kwargs):
        self.calls += 1
        choice = kwargs.get("tool_choice", "auto")
        if choice == "none" or self.calls > 1:
            return LLMToolResponse(
                content=(
                    "Listed company docs, loaded handbook metadata, "
                    "summarized it, and answered the leave question from the document."
                ),
                tool_calls=(),
                model="smoke-fake",
                usage=None,
            )
        return LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="1", name="list_company_documents", arguments={}),
                ToolCall(
                    id="2",
                    name="get_company_document",
                    arguments={"document_id": 42},
                ),
                ToolCall(
                    id="3",
                    name="summarize_document",
                    arguments={"document_id": 42, "document_type": "company"},
                ),
                ToolCall(
                    id="4",
                    name="ask_about_document",
                    arguments={
                        "document_id": 42,
                        "document_type": "company",
                        "question": "What is annual leave?",
                    },
                ),
            ),
            model="smoke-fake",
            usage=None,
        )

    def generate_text(self, *args, **kwargs):
        return LLMTextResponse(content="", model="smoke-fake")

    def generate_structured(self, *args, **kwargs):
        return LLMStructuredResponse(data={}, model="smoke-fake")


def main() -> None:
    company = MagicMock()
    company.list_documents_for_access.return_value = [_company_doc()]
    company.get_document_for_access.return_value = _company_doc()
    company.list_categories.return_value = []

    understanding = MagicMock()
    understanding.summarize_document.return_value = DocumentSummary(
        title="Employee Handbook",
        summary="Covers leave and conduct.",
        key_points=["Annual leave policy"],
        important_dates=[],
        action_items=[],
        document_id=42,
        source_type=DocumentSourceType.COMPANY,
    )
    understanding.answer_question_about_document.return_value = DocumentAnswer(
        answer="Annual leave is described in the handbook.",
        citations=[DocumentCitation(page_number=1, excerpt="annual leave")],
        document_id=42,
        source_type=DocumentSourceType.COMPANY,
    )

    agent = build_documents_agent(
        llm_provider=_ScriptedLLM(),
        company_documents=company,
        employee_documents=MagicMock(),
        private_documents=MagicMock(),
        understanding=understanding,
    )
    context = AIExecutionContext(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"company_documents:read"}),
        employee_id=10,
        candidate_id=None,
    )
    result = agent.ask(
        DocumentsAgentRequest(
            question=(
                "List company documents, open the handbook, summarize it, "
                "and ask what it says about annual leave."
            ),
            context=context,
        )
    )
    print("agent_id:", result.agent_id)
    print("tools:", result.tool_names_called)
    print("pending_confirmation:", result.pending_confirmation)
    print("answer:", result.answer)
    assert result.agent_id == "documents"
    assert result.pending_confirmation is None
    assert "storage_key" not in result.answer.lower()
    assert company.list_documents_for_access.called
    assert company.get_document_for_access.called
    assert understanding.summarize_document.called
    assert understanding.answer_question_about_document.called
    print("SMOKE_DOCUMENT_AGENT_OK")


if __name__ == "__main__":
    main()
