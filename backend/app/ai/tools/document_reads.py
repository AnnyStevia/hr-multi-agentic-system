"""Document Agent read tools — wrap document services + DocumentUnderstandingService only."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext
from app.ai.documents import (
    DocumentRef,
    DocumentSourceType,
    DocumentUnderstandingService,
)
from app.ai.documents.exceptions import (
    DocumentUnderstandingAuthorizationError,
    DocumentUnderstandingError,
    DocumentUnderstandingNotFoundError,
    DocumentUnderstandingUnsupportedError,
    DocumentUnderstandingValidationError,
)
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.documents.library_service import (
    CompanyDocumentService,
    PrivateDocumentService,
    build_company_document_response,
    build_private_document_response,
)
from app.modules.documents.service import DocumentService, build_document_response
from app.modules.identity.hr_access import HR_STAFF_ROLE_NAMES
from app.shared.exceptions import AppException

_COMPANY_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset({"company_documents:read"}),
    operates_on_current_user=False,
)

_SELF_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset(),
    operates_on_current_user=True,
)

_HR_EMPLOYEE_DOCS_META = ToolMetadata(
    operation="read",
    required_roles=frozenset({"hr", "admin"}),
    required_permissions=frozenset({"documents:read"}),
    operates_on_current_user=False,
)

_UNDERSTANDING_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset(),
    operates_on_current_user=False,
)


def _call_service(fn, *, error_message: str):
    try:
        return fn()
    except AppException as exc:
        msg = (exc.message or "").strip() or error_message
        lowered = msg.lower()
        if any(
            token in lowered
            for token in ("sqlalchemy", "traceback", "psycopg", "operationalerror")
        ):
            raise ToolExecutionError(error_message) from exc
        raise ToolExecutionError(msg) from exc
    except (
        DocumentUnderstandingAuthorizationError,
        DocumentUnderstandingNotFoundError,
        DocumentUnderstandingUnsupportedError,
        DocumentUnderstandingValidationError,
        DocumentUnderstandingError,
    ) as exc:
        raise ToolExecutionError(exc.message or error_message) from exc
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(error_message) from exc


def _include_archived(context: AIExecutionContext) -> bool:
    return bool(context.role_names.intersection(HR_STAFF_ROLE_NAMES))


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompanyDocumentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    description: str | None = None
    category_id: int
    category_slug: str
    category_label: str
    filename: str
    content_type: str
    size_bytes: int
    version: int
    status: str
    rag_index_status: str
    created_at: datetime
    updated_at: datetime


class CompanyDocumentList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[CompanyDocumentBrief] = Field(default_factory=list)


class CompanyDocumentCategoryBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    slug: str
    label: str
    sort_order: int


class CompanyDocumentCategoryList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[CompanyDocumentCategoryBrief] = Field(default_factory=list)


class PrivateDocumentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    description: str | None = None
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime


class PrivateDocumentList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[PrivateDocumentBrief] = Field(default_factory=list)


class EmployeeDocumentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    employee_id: int
    document_type: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class EmployeeDocumentList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[EmployeeDocumentBrief] = Field(default_factory=list)


class DocumentTypeArg(str, Enum):
    COMPANY = "company"
    EMPLOYEE = "employee"
    PRIVATE = "private"


class SummarizeDocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(ge=1)
    document_type: DocumentTypeArg
    employee_id: int | None = Field(default=None, ge=1)


class AskAboutDocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(ge=1)
    document_type: DocumentTypeArg
    question: str = Field(min_length=1, max_length=2000)
    employee_id: int | None = Field(default=None, ge=1)


class GetCompanyDocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(ge=1)


class ListEmployeeDocumentsForHrInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: int = Field(ge=1)


class DocumentSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    important_dates: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    document_id: int | None = None
    document_type: str | None = None
    truncated: bool = False


class DocumentCitationBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int
    excerpt: str | None = None


class DocumentAnswerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[DocumentCitationBrief] = Field(default_factory=list)
    document_id: int | None = None
    document_type: str | None = None
    truncated: bool = False


def _company_brief(document) -> CompanyDocumentBrief:
    resp = build_company_document_response(document)
    status = resp.status.value if hasattr(resp.status, "value") else str(resp.status)
    rag = (
        resp.rag_index_status.value
        if hasattr(resp.rag_index_status, "value")
        else str(resp.rag_index_status)
    )
    return CompanyDocumentBrief(
        id=resp.id,
        title=resp.title,
        description=resp.description,
        category_id=resp.category_id,
        category_slug=resp.category_slug,
        category_label=resp.category_label,
        filename=resp.original_filename,
        content_type=resp.content_type,
        size_bytes=resp.size_bytes,
        version=resp.version,
        status=status,
        rag_index_status=rag,
        created_at=resp.created_at,
        updated_at=resp.updated_at,
    )


def _private_brief(document) -> PrivateDocumentBrief:
    resp = build_private_document_response(document)
    return PrivateDocumentBrief(
        id=resp.id,
        title=resp.title,
        description=resp.description,
        filename=resp.original_filename,
        content_type=resp.content_type,
        size_bytes=resp.size_bytes,
        created_at=resp.created_at,
        updated_at=resp.updated_at,
    )


def _employee_brief(document) -> EmployeeDocumentBrief:
    resp = build_document_response(document)
    doc_type = (
        resp.document_type.value
        if hasattr(resp.document_type, "value")
        else str(resp.document_type)
    )
    return EmployeeDocumentBrief(
        id=resp.id,
        employee_id=resp.employee_id,
        document_type=doc_type,
        filename=resp.original_filename,
        content_type=resp.content_type,
        size_bytes=resp.size_bytes,
        uploaded_at=resp.uploaded_at,
    )


def _to_document_ref(
    document_id: int,
    document_type: DocumentTypeArg,
    employee_id: int | None,
) -> DocumentRef:
    source = DocumentSourceType(document_type.value)
    ref_employee_id = employee_id if source == DocumentSourceType.EMPLOYEE else None
    return DocumentRef(
        source_type=source,
        document_id=document_id,
        employee_id=ref_employee_id,
    )


class ListCompanyDocumentsTool(BaseTool):
    name = "list_company_documents"
    description = (
        "List authorized company library documents (metadata only: title, category, "
        "status, filename, rag_index_status). Requires company_documents:read. "
        "Non-HR callers only see ACTIVE documents. Does not return file content, "
        "storage keys, or download URLs."
    )
    metadata = _COMPANY_META
    input_model = EmptyInput
    output_model = CompanyDocumentList

    def __init__(self, company_service: CompanyDocumentService) -> None:
        self._company = company_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, EmptyInput)
        rows = _call_service(
            lambda: self._company.list_documents_for_access(
                include_archived=_include_archived(context)
            ),
            error_message="Unable to list company documents",
        )
        return CompanyDocumentList(documents=[_company_brief(row) for row in rows])


class GetCompanyDocumentTool(BaseTool):
    name = "get_company_document"
    description = (
        "Get metadata for one company library document by document_id. "
        "Requires company_documents:read. Does not download file bytes. "
        "Archived documents are hidden from non-HR callers."
    )
    metadata = _COMPANY_META
    input_model = GetCompanyDocumentInput
    output_model = CompanyDocumentBrief

    def __init__(self, company_service: CompanyDocumentService) -> None:
        self._company = company_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetCompanyDocumentInput)
        row = _call_service(
            lambda: self._company.get_document_for_access(
                args.document_id,
                include_archived=_include_archived(context),
            ),
            error_message="Unable to load company document",
        )
        return _company_brief(row)


class ListCompanyDocumentCategoriesTool(BaseTool):
    name = "list_company_document_categories"
    description = (
        "List company document categories (slug, label). "
        "Requires company_documents:read. Metadata only."
    )
    metadata = _COMPANY_META
    input_model = EmptyInput
    output_model = CompanyDocumentCategoryList

    def __init__(self, company_service: CompanyDocumentService) -> None:
        self._company = company_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, EmptyInput)
        rows = _call_service(
            lambda: self._company.list_categories(),
            error_message="Unable to list document categories",
        )
        return CompanyDocumentCategoryList(
            categories=[
                CompanyDocumentCategoryBrief(
                    id=row.id,
                    slug=row.slug,
                    label=row.label,
                    sort_order=row.sort_order,
                )
                for row in rows
            ]
        )


class ListMyPrivateDocumentsTool(BaseTool):
    name = "list_my_private_documents"
    description = (
        "List ONLY the authenticated user's own private documents (metadata). "
        "Identity comes from the session — never accepts owner_id, employee_id, or user_id. "
        "HR cannot override private ownership. No file bytes or storage keys."
    )
    metadata = _SELF_META
    input_model = EmptyInput
    output_model = PrivateDocumentList

    def __init__(self, private_service: PrivateDocumentService) -> None:
        self._private = private_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, EmptyInput)
        rows = _call_service(
            lambda: self._private.list_for_user(context.user_id),
            error_message="Unable to list your private documents",
        )
        return PrivateDocumentList(documents=[_private_brief(row) for row in rows])


class ListMyEmployeeDocumentsTool(BaseTool):
    name = "list_my_employee_documents"
    description = (
        "List ONLY the authenticated employee's own HR/onboarding documents (metadata). "
        "Identity comes from the session — never accepts employee_id or user_id. "
        "No file bytes or storage keys."
    )
    metadata = _SELF_META
    input_model = EmptyInput
    output_model = EmployeeDocumentList

    def __init__(self, employee_service: DocumentService) -> None:
        self._employees = employee_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, EmptyInput)
        rows = _call_service(
            lambda: self._employees.list_for_user(context.user_id),
            error_message="Unable to list your employee documents",
        )
        return EmployeeDocumentList(documents=[_employee_brief(row) for row in rows])


class ListEmployeeDocumentsForHrTool(BaseTool):
    name = "list_employee_documents_for_hr"
    description = (
        "HR/Admin only: list HR/onboarding documents for a given employee_id (metadata). "
        "Requires HR or Admin staff role AND documents:read. "
        "Managers cannot use this tool. No file bytes or storage keys."
    )
    metadata = _HR_EMPLOYEE_DOCS_META
    input_model = ListEmployeeDocumentsForHrInput
    output_model = EmployeeDocumentList

    def __init__(self, employee_service: DocumentService) -> None:
        self._employees = employee_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListEmployeeDocumentsForHrInput)
        rows = _call_service(
            lambda: self._employees.list_for_employee(args.employee_id),
            error_message="Unable to list employee documents",
        )
        return EmployeeDocumentList(documents=[_employee_brief(row) for row in rows])


class SummarizeDocumentTool(BaseTool):
    name = "summarize_document"
    description = (
        "Summarize one authorized PDF document (company, employee, or private). "
        "Uses Document Understanding — returns structured title/summary/key_points/"
        "important_dates/action_items. Requires document_id and document_type. "
        "Optional employee_id only when summarizing another employee's document as HR. "
        "Does not support candidate application/CV documents. Never invent fields."
    )
    metadata = _UNDERSTANDING_META
    input_model = SummarizeDocumentInput
    output_model = DocumentSummaryOutput

    def __init__(self, understanding: DocumentUnderstandingService) -> None:
        self._understanding = understanding

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, SummarizeDocumentInput)
        ref = _to_document_ref(args.document_id, args.document_type, args.employee_id)
        summary = _call_service(
            lambda: self._understanding.summarize_document(ref, context),
            error_message="Unable to summarize document",
        )
        return DocumentSummaryOutput(
            title=summary.title,
            summary=summary.summary,
            key_points=list(summary.key_points),
            important_dates=list(summary.important_dates),
            action_items=list(summary.action_items),
            document_id=summary.document_id,
            document_type=(
                summary.source_type.value if summary.source_type else None
            ),
            truncated=summary.truncated,
        )


class AskAboutDocumentTool(BaseTool):
    name = "ask_about_document"
    description = (
        "Ask a grounded question about one authorized PDF (company, employee, or private). "
        "Returns answer + page citations. Does not use general knowledge. "
        "Does not support candidate application/CV documents. "
        "Optional employee_id only for HR peer employee documents."
    )
    metadata = _UNDERSTANDING_META
    input_model = AskAboutDocumentInput
    output_model = DocumentAnswerOutput

    def __init__(self, understanding: DocumentUnderstandingService) -> None:
        self._understanding = understanding

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, AskAboutDocumentInput)
        ref = _to_document_ref(args.document_id, args.document_type, args.employee_id)
        answer = _call_service(
            lambda: self._understanding.answer_question_about_document(
                ref, args.question, context
            ),
            error_message="Unable to answer from document",
        )
        return DocumentAnswerOutput(
            answer=answer.answer,
            citations=[
                DocumentCitationBrief(
                    page_number=c.page_number, excerpt=c.excerpt
                )
                for c in answer.citations
            ],
            document_id=answer.document_id,
            document_type=(
                answer.source_type.value if answer.source_type else None
            ),
            truncated=answer.truncated,
        )
