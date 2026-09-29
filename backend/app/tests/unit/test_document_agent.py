"""Unit tests for Document Agent read tools + agent (Phase 11.2B)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.agents.documents import (
    DOCUMENTS_AGENT_ID,
    DocumentsAgent,
    DocumentsAgentAuthorizationError,
    DocumentsAgentRequest,
    DocumentsAgentValidationError,
    build_documents_agent,
)
from app.ai.agents.documents.prompts import DOCUMENTS_AGENT_SYSTEM_PROMPT
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMStructuredResponse, LLMTextResponse, LLMToolResponse, ToolCall
from app.ai.documents import DocumentAnswer, DocumentSourceType, DocumentSummary
from app.ai.documents.schemas import DocumentCitation
from app.ai.tools.authorization import authorize_tool
from app.ai.tools.document_reads import (
    AskAboutDocumentInput,
    AskAboutDocumentTool,
    EmptyInput,
    GetCompanyDocumentInput,
    GetCompanyDocumentTool,
    ListCompanyDocumentCategoriesTool,
    ListCompanyDocumentsTool,
    ListEmployeeDocumentsForHrInput,
    ListEmployeeDocumentsForHrTool,
    ListMyEmployeeDocumentsTool,
    ListMyPrivateDocumentsTool,
    SummarizeDocumentInput,
    SummarizeDocumentTool,
)
from app.ai.tools.exceptions import ToolAuthorizationError, ToolExecutionError
from app.ai.tools.executor import ToolExecutor
from app.ai.tools.registry import ToolRegistry
from app.modules.documents.models import (
    CompanyDocumentRagIndexStatus,
    CompanyDocumentStatus,
    DocumentType,
)
from app.shared.exceptions import AppException


def _ctx(
    *,
    roles: set[str],
    permissions: set[str],
    user_id: int = 1,
    employee_id: int | None = 10,
) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset(roles),
        permission_names=frozenset(permissions),
        employee_id=employee_id,
        candidate_id=None,
    )


def _company_doc(**overrides):
    now = datetime.now(UTC)
    values = {
        "id": 42,
        "title": "Handbook",
        "description": "Rules",
        "category_id": 1,
        "category": SimpleNamespace(slug="policies", label="Policies"),
        "original_filename": "handbook.pdf",
        "content_type": "application/pdf",
        "size_bytes": 100,
        "version": 1,
        "uploaded_by_user_id": 1,
        "uploaded_by": SimpleNamespace(first_name="A", last_name="B"),
        "status": CompanyDocumentStatus.ACTIVE,
        "rag_index_status": CompanyDocumentRagIndexStatus.READY,
        "rag_indexed_at": now,
        "rag_indexing_error": None,
        "created_at": now,
        "updated_at": now,
        "storage_key": "company-documents/42/handbook.pdf",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _private_doc(**overrides):
    now = datetime.now(UTC)
    values = {
        "id": 7,
        "owner_employee_id": 10,
        "title": "Notes",
        "description": None,
        "original_filename": "notes.pdf",
        "content_type": "application/pdf",
        "size_bytes": 50,
        "uploaded_by_user_id": 1,
        "created_at": now,
        "updated_at": now,
        "storage_key": "secret-key",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _employee_doc(**overrides):
    now = datetime.now(UTC)
    values = {
        "id": 3,
        "employee_id": 10,
        "document_type": DocumentType.ID_DOCUMENT,
        "original_filename": "id.pdf",
        "content_type": "application/pdf",
        "size_bytes": 20,
        "uploaded_at": now,
        "created_at": now,
        "updated_at": now,
        "storage_key": "emp-key",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_list_company_documents_requires_permission():
    tool = ListCompanyDocumentsTool(MagicMock())
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(tool, _ctx(roles={"employee"}, permissions=set()), EmptyInput())


def test_list_company_active_for_employee_no_storage_key():
    company = MagicMock()
    company.list_documents_for_access.return_value = [_company_doc()]
    tool = ListCompanyDocumentsTool(company)
    ctx = _ctx(roles={"employee"}, permissions={"company_documents:read"})
    authorize_tool(tool, ctx, EmptyInput())
    out = tool.execute(ctx, EmptyInput())
    assert len(out.documents) == 1
    dumped = out.documents[0].model_dump()
    assert "storage_key" not in dumped
    assert dumped["status"] == "active"
    company.list_documents_for_access.assert_called_once_with(include_archived=False)


def test_list_company_hr_include_archived_flag():
    company = MagicMock()
    company.list_documents_for_access.return_value = []
    tool = ListCompanyDocumentsTool(company)
    ctx = _ctx(roles={"hr"}, permissions={"company_documents:read"})
    tool.execute(ctx, EmptyInput())
    company.list_documents_for_access.assert_called_once_with(include_archived=True)


def test_get_company_archived_hidden_from_employee():
    company = MagicMock()
    company.get_document_for_access.side_effect = AppException(
        "Document not found", status_code=404
    )
    tool = GetCompanyDocumentTool(company)
    ctx = _ctx(roles={"employee"}, permissions={"company_documents:read"})
    with pytest.raises(ToolExecutionError):
        tool.execute(ctx, GetCompanyDocumentInput(document_id=9))


def test_manager_company_list_active_only_when_permitted():
    company = MagicMock()
    company.list_documents_for_access.return_value = [_company_doc()]
    tool = ListCompanyDocumentsTool(company)
    ctx = _ctx(roles={"manager"}, permissions={"company_documents:read"})
    authorize_tool(tool, ctx, EmptyInput())
    tool.execute(ctx, EmptyInput())
    company.list_documents_for_access.assert_called_once_with(include_archived=False)


def test_private_owner_list_ok():
    private = MagicMock()
    private.list_for_user.return_value = [_private_doc()]
    tool = ListMyPrivateDocumentsTool(private)
    ctx = _ctx(roles={"employee"}, permissions=set(), user_id=5, employee_id=50)
    authorize_tool(tool, ctx, EmptyInput())
    out = tool.execute(ctx, EmptyInput())
    assert out.documents[0].id == 7
    assert "storage_key" not in out.documents[0].model_dump()
    private.list_for_user.assert_called_once_with(5)


def test_employee_self_list_ok():
    employees = MagicMock()
    employees.list_for_user.return_value = [_employee_doc()]
    tool = ListMyEmployeeDocumentsTool(employees)
    ctx = _ctx(roles={"employee"}, permissions=set(), user_id=2, employee_id=20)
    out = tool.execute(ctx, EmptyInput())
    assert out.documents[0].id == 3
    employees.list_for_user.assert_called_once_with(2)


def test_manager_denied_hr_employee_lookup():
    tool = ListEmployeeDocumentsForHrTool(MagicMock())
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            tool,
            _ctx(
                roles={"manager"},
                permissions={"documents:read"},
                user_id=8,
                employee_id=80,
            ),
            ListEmployeeDocumentsForHrInput(employee_id=99),
        )


def test_hr_employee_lookup_ok():
    employees = MagicMock()
    employees.list_for_employee.return_value = [_employee_doc(employee_id=99)]
    tool = ListEmployeeDocumentsForHrTool(employees)
    ctx = _ctx(
        roles={"hr"},
        permissions={"documents:read"},
        user_id=1,
        employee_id=1,
    )
    authorize_tool(tool, ctx, ListEmployeeDocumentsForHrInput(employee_id=99))
    out = tool.execute(ctx, ListEmployeeDocumentsForHrInput(employee_id=99))
    assert out.documents[0].employee_id == 99
    employees.list_for_employee.assert_called_once_with(99)


def test_summarize_company_document():
    understanding = MagicMock()
    understanding.summarize_document.return_value = DocumentSummary(
        title="Handbook",
        summary="Overview",
        key_points=["Leave"],
        important_dates=[],
        action_items=[],
        document_id=42,
        source_type=DocumentSourceType.COMPANY,
    )
    tool = SummarizeDocumentTool(understanding)
    ctx = _ctx(roles={"employee"}, permissions={"company_documents:read"})
    out = tool.execute(
        ctx,
        SummarizeDocumentInput(document_id=42, document_type="company"),
    )
    assert out.title == "Handbook"
    assert out.important_dates == []
    assert "storage_key" not in out.model_dump()
    ref = understanding.summarize_document.call_args.args[0]
    assert ref.source_type == DocumentSourceType.COMPANY
    assert ref.employee_id is None


def test_ask_about_document_citations():
    understanding = MagicMock()
    understanding.answer_question_about_document.return_value = DocumentAnswer(
        answer="Leave requires approval.",
        citations=[DocumentCitation(page_number=1, excerpt="Leave policy")],
        document_id=42,
        source_type=DocumentSourceType.COMPANY,
    )
    tool = AskAboutDocumentTool(understanding)
    ctx = _ctx(roles={"employee"}, permissions={"company_documents:read"})
    out = tool.execute(
        ctx,
        AskAboutDocumentInput(
            document_id=42,
            document_type="company",
            question="What is leave?",
        ),
    )
    assert out.citations[0].page_number == 1


def test_application_document_type_rejected_on_input():
    with pytest.raises(Exception):
        SummarizeDocumentInput.model_validate(
            {"document_id": 1, "document_type": "application"}
        )


def test_private_summarize_strips_employee_id_from_ref():
    understanding = MagicMock()
    understanding.summarize_document.return_value = DocumentSummary(
        title="Notes",
        summary="x",
        document_id=7,
        source_type=DocumentSourceType.PRIVATE,
    )
    tool = SummarizeDocumentTool(understanding)
    ctx = _ctx(roles={"employee"}, permissions=set(), user_id=5, employee_id=50)
    tool.execute(
        ctx,
        SummarizeDocumentInput(
            document_id=7,
            document_type="private",
            employee_id=999,
        ),
    )
    ref = understanding.summarize_document.call_args.args[0]
    assert ref.employee_id is None


def test_agent_registers_only_read_tools():
    agent = build_documents_agent(
        llm_provider=MagicMock(),
        company_documents=MagicMock(),
        employee_documents=MagicMock(),
        private_documents=MagicMock(),
        understanding=MagicMock(),
    )
    names = agent.tool_names()
    assert names == sorted(
        [
            "ask_about_document",
            "get_company_document",
            "list_company_document_categories",
            "list_company_documents",
            "list_employee_documents_for_hr",
            "list_my_employee_documents",
            "list_my_private_documents",
            "summarize_document",
        ]
    )
    assert all(
        "upload" not in n and "delete" not in n and "archive" not in n for n in names
    )


def test_agent_ask_empty_rejected():
    agent = DocumentsAgent(
        llm_provider=MagicMock(),
        company_documents=MagicMock(),
        employee_documents=MagicMock(),
        private_documents=MagicMock(),
        understanding=MagicMock(),
    )
    with pytest.raises(DocumentsAgentValidationError):
        agent.ask(
            DocumentsAgentRequest(
                question="  ",
                context=_ctx(roles={"employee"}, permissions=set()),
            )
        )


def test_prompt_injection_hardening_present():
    assert "DATA" in DOCUMENTS_AGENT_SYSTEM_PROMPT
    assert "instructions" in DOCUMENTS_AGENT_SYSTEM_PROMPT
    assert "READ-ONLY" in DOCUMENTS_AGENT_SYSTEM_PROMPT


def test_agent_ask_read_only_roundtrip_mocked():
    company = MagicMock()
    company.list_documents_for_access.return_value = [_company_doc()]

    class _FakeLLM:
        def __init__(self):
            self.calls = 0

        def generate_with_tools(self, messages, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMToolResponse(
                    content=None,
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="list_company_documents",
                            arguments={},
                        ),
                    ),
                    model="fake",
                    usage=None,
                )
            return LLMToolResponse(
                content="Here are your company documents.",
                tool_calls=(),
                model="fake",
                usage=None,
            )

        def generate_text(self, *args, **kwargs):
            return LLMTextResponse(content="", model="fake")

        def generate_structured(self, *args, **kwargs):
            return LLMStructuredResponse(data={}, model="fake")

    agent = build_documents_agent(
        llm_provider=_FakeLLM(),
        company_documents=company,
        employee_documents=MagicMock(),
        private_documents=MagicMock(),
        understanding=MagicMock(),
    )
    result = agent.ask(
        DocumentsAgentRequest(
            question="Show me the company documents",
            context=_ctx(
                roles={"employee"}, permissions={"company_documents:read"}
            ),
        )
    )
    assert result.agent_id == DOCUMENTS_AGENT_ID
    assert result.pending_confirmation is None
    assert "list_company_documents" in result.tool_names_called
    assert "storage_key" not in result.answer
    assert result.document_summary is None
    assert result.document_answer is None


def test_agent_ask_surfaces_structured_summary():
    understanding = MagicMock()
    understanding.summarize_document.return_value = DocumentSummary(
        title="Handbook",
        summary="Company rules overview.",
        key_points=["Be on time"],
        important_dates=["2026-01-01"],
        action_items=["Read section 3"],
        document_id=42,
        source_type=DocumentSourceType.COMPANY,
        truncated=False,
        model="fake",
    )

    class _FakeLLM:
        def __init__(self):
            self.calls = 0

        def generate_with_tools(self, messages, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMToolResponse(
                    content=None,
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="summarize_document",
                            arguments={
                                "document_id": 42,
                                "document_type": "company",
                            },
                        ),
                    ),
                    model="fake",
                    usage=None,
                )
            return LLMToolResponse(
                content="Here is a summary of the handbook.",
                tool_calls=(),
                model="fake",
                usage=None,
            )

        def generate_text(self, *args, **kwargs):
            return LLMTextResponse(content="", model="fake")

        def generate_structured(self, *args, **kwargs):
            return LLMStructuredResponse(data={}, model="fake")

    agent = build_documents_agent(
        llm_provider=_FakeLLM(),
        company_documents=MagicMock(),
        employee_documents=MagicMock(),
        private_documents=MagicMock(),
        understanding=understanding,
    )
    result = agent.ask(
        DocumentsAgentRequest(
            question="Summarize document_id=42 document_type=company",
            context=_ctx(
                roles={"employee"}, permissions={"company_documents:read"}
            ),
        )
    )
    assert "summarize_document" in result.tool_names_called
    assert result.document_summary is not None
    assert result.document_summary.title == "Handbook"
    assert result.document_summary.key_points == ["Be on time"]
    assert result.document_summary.document_id == 42
    assert result.document_answer is None


def test_agent_ask_surfaces_structured_answer_with_citations():
    understanding = MagicMock()
    understanding.answer_question_about_document.return_value = DocumentAnswer(
        answer="Employees get 18 days of leave.",
        citations=[
            DocumentCitation(page_number=14, excerpt="18 days of annual leave")
        ],
        document_id=42,
        source_type=DocumentSourceType.COMPANY,
        truncated=False,
        has_context=True,
        model="fake",
    )

    class _FakeLLM:
        def __init__(self):
            self.calls = 0

        def generate_with_tools(self, messages, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMToolResponse(
                    content=None,
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="ask_about_document",
                            arguments={
                                "document_id": 42,
                                "document_type": "company",
                                "question": "What is the annual leave policy?",
                            },
                        ),
                    ),
                    model="fake",
                    usage=None,
                )
            return LLMToolResponse(
                content="Employees get 18 days of leave.",
                tool_calls=(),
                model="fake",
                usage=None,
            )

        def generate_text(self, *args, **kwargs):
            return LLMTextResponse(content="", model="fake")

        def generate_structured(self, *args, **kwargs):
            return LLMStructuredResponse(data={}, model="fake")

    agent = build_documents_agent(
        llm_provider=_FakeLLM(),
        company_documents=MagicMock(),
        employee_documents=MagicMock(),
        private_documents=MagicMock(),
        understanding=understanding,
    )
    result = agent.ask(
        DocumentsAgentRequest(
            question="Ask about document_id=42 document_type=company: leave?",
            context=_ctx(
                roles={"employee"}, permissions={"company_documents:read"}
            ),
        )
    )
    assert result.document_answer is not None
    assert result.document_answer.answer.startswith("Employees get 18")
    assert result.document_answer.citations[0].page_number == 14
    assert result.document_summary is None


def test_agent_ask_failed_understanding_promotes_auth_error():
    from app.ai.documents.exceptions import DocumentUnderstandingAuthorizationError

    understanding = MagicMock()
    understanding.summarize_document.side_effect = (
        DocumentUnderstandingAuthorizationError(
            "Not authorized to access this document"
        )
    )

    class _FakeLLM:
        def __init__(self):
            self.calls = 0

        def generate_with_tools(self, messages, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMToolResponse(
                    content=None,
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="summarize_document",
                            arguments={
                                "document_id": 99,
                                "document_type": "company",
                            },
                        ),
                    ),
                    model="fake",
                    usage=None,
                )
            return LLMToolResponse(
                content="I cannot access that document.",
                tool_calls=(),
                model="fake",
                usage=None,
            )

        def generate_text(self, *args, **kwargs):
            return LLMTextResponse(content="", model="fake")

        def generate_structured(self, *args, **kwargs):
            return LLMStructuredResponse(data={}, model="fake")

    agent = build_documents_agent(
        llm_provider=_FakeLLM(),
        company_documents=MagicMock(),
        employee_documents=MagicMock(),
        private_documents=MagicMock(),
        understanding=understanding,
    )
    with pytest.raises(DocumentsAgentAuthorizationError):
        agent.ask(
            DocumentsAgentRequest(
                question="Summarize document_id=99 document_type=company",
                context=_ctx(
                    roles={"employee"}, permissions={"company_documents:read"}
                ),
            )
        )


def test_domain_get_for_access_archived():
    from app.modules.documents.library_service import CompanyDocumentService

    repo = MagicMock()
    storage = MagicMock()
    repo.get_by_id.return_value = _company_doc(status=CompanyDocumentStatus.ARCHIVED)
    service = CompanyDocumentService(repo, storage)
    with pytest.raises(AppException) as exc:
        service.get_document_for_access(42, include_archived=False)
    assert exc.value.status_code == 404
    doc = service.get_document_for_access(42, include_archived=True)
    assert doc.status == CompanyDocumentStatus.ARCHIVED


def test_categories_tool():
    company = MagicMock()
    company.list_categories.return_value = [
        SimpleNamespace(id=1, slug="policies", label="Policies", sort_order=1)
    ]
    tool = ListCompanyDocumentCategoriesTool(company)
    ctx = _ctx(roles={"employee"}, permissions={"company_documents:read"})
    out = tool.execute(ctx, EmptyInput())
    assert out.categories[0].slug == "policies"


def test_executor_wires_list_company():
    company = MagicMock()
    company.list_documents_for_access.return_value = [_company_doc()]
    registry = ToolRegistry()
    registry.register(ListCompanyDocumentsTool(company))
    result = ToolExecutor(registry).execute(
        _ctx(roles={"employee"}, permissions={"company_documents:read"}),
        "list_company_documents",
        {},
    )
    assert result.success is True
    assert "storage_key" not in str(result.data)
