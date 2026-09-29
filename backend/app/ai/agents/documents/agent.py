"""Document Agent — read-only tools over document services + Document Understanding."""

from __future__ import annotations

from app.ai.agents.documents.exceptions import (
    DocumentsAgentAuthorizationError,
    DocumentsAgentError,
    DocumentsAgentValidationError,
)
from app.ai.agents.documents.prompts import DOCUMENTS_AGENT_SYSTEM_PROMPT
from app.ai.agents.documents.schemas import (
    DOCUMENTS_AGENT_ID,
    DocumentsAgentAnswer,
    DocumentsAgentDocumentAnswer,
    DocumentsAgentDocumentSummary,
    DocumentsAgentRequest,
    DocumentsAgentUsage,
)
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm.base import LLMProvider
from app.ai.documents import DocumentUnderstandingService
from app.ai.orchestration.tool_roundtrip import run_tool_roundtrip
from app.ai.tools.document_reads import (
    AskAboutDocumentTool,
    GetCompanyDocumentTool,
    ListCompanyDocumentCategoriesTool,
    ListCompanyDocumentsTool,
    ListEmployeeDocumentsForHrTool,
    ListMyEmployeeDocumentsTool,
    ListMyPrivateDocumentsTool,
    SummarizeDocumentTool,
)
from app.ai.tools.exceptions import (
    ToolAuthorizationError,
    ToolExecutionError,
    ToolValidationError,
)
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.schemas import ToolResult
from app.modules.documents.library_service import (
    CompanyDocumentService,
    PrivateDocumentService,
)
from app.modules.documents.service import DocumentService

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_MAX_TOOL_CALLS = 8

_UNDERSTANDING_TOOLS = frozenset({"summarize_document", "ask_about_document"})

_AUTH_TOKENS = (
    "not authorized",
    "unauthorized",
    "permission",
    "forbidden",
    "access denied",
    "not allowed",
    "only you",
    "owner",
)

_VALIDATION_TOKENS = (
    "not found",
    "archived",
    "unsupported",
    "not a pdf",
    "application/pdf",
    "malformed",
    "empty",
    "invalid",
    "must not be empty",
    "must be",
    "candidate",
    "application",
)


class DocumentsAgent:
    """Read-only documents assistant (metadata + understanding). No writes."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        company_documents: CompanyDocumentService,
        employee_documents: DocumentService,
        private_documents: PrivateDocumentService,
        understanding: DocumentUnderstandingService,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    ) -> None:
        self._llm = llm_provider
        self._max_output_tokens = max_output_tokens
        self._max_tool_calls = max_tool_calls
        self._registry = ToolRegistry()
        self._registry.register(ListCompanyDocumentsTool(company_documents))
        self._registry.register(GetCompanyDocumentTool(company_documents))
        self._registry.register(ListCompanyDocumentCategoriesTool(company_documents))
        self._registry.register(ListMyPrivateDocumentsTool(private_documents))
        self._registry.register(ListMyEmployeeDocumentsTool(employee_documents))
        self._registry.register(ListEmployeeDocumentsForHrTool(employee_documents))
        self._registry.register(SummarizeDocumentTool(understanding))
        self._registry.register(AskAboutDocumentTool(understanding))

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def agent_id(self) -> str:
        return DOCUMENTS_AGENT_ID

    def ask(self, request: DocumentsAgentRequest) -> DocumentsAgentAnswer:
        question = (request.question or "").strip()
        if not question:
            raise DocumentsAgentValidationError("Question must not be empty")

        try:
            result = run_tool_roundtrip(
                provider=self._llm,
                context=request.context,
                registry=self._registry,
                user_prompt=question,
                system_prompt=DOCUMENTS_AGENT_SYSTEM_PROMPT,
                tool_choice="auto",
                max_tokens=self._max_output_tokens,
                max_tool_calls=self._max_tool_calls,
            )
        except ToolAuthorizationError as exc:
            raise DocumentsAgentAuthorizationError(str(exc)) from exc
        except ToolValidationError as exc:
            raise DocumentsAgentValidationError(str(exc)) from exc
        except ToolExecutionError as exc:
            self._raise_from_tool_message(str(exc))
        except LLMConfigurationError as exc:
            raise DocumentsAgentError("Documents agent is not configured") from exc
        except LLMProviderError as exc:
            raise DocumentsAgentError("Documents agent failed") from exc

        document_summary, document_answer = self._harvest_understanding(
            result.tool_results
        )

        # Read-only: ignore any accidental confirmation tokens.
        answer = (result.final_content or "").strip()
        if not answer:
            if document_answer is not None and document_answer.answer:
                answer = document_answer.answer
            elif document_summary is not None and document_summary.summary:
                answer = document_summary.summary
            else:
                answer = "I don't have enough information to answer that."

        usage = None
        if result.usage is not None:
            usage = DocumentsAgentUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                thinking_tokens=result.usage.thinking_tokens,
                total_tokens=result.usage.total_tokens,
            )

        return DocumentsAgentAnswer(
            answer=answer,
            agent_id=DOCUMENTS_AGENT_ID,
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=usage,
            pending_confirmation=None,
            document_summary=document_summary,
            document_answer=document_answer,
        )

    def tool_names(self) -> list[str]:
        return [tool.name for tool in self._registry.list_tools()]

    def _harvest_understanding(
        self, tool_results: tuple[ToolResult, ...]
    ) -> tuple[
        DocumentsAgentDocumentSummary | None,
        DocumentsAgentDocumentAnswer | None,
    ]:
        document_summary: DocumentsAgentDocumentSummary | None = None
        document_answer: DocumentsAgentDocumentAnswer | None = None
        last_understanding: ToolResult | None = None

        for tool_result in tool_results:
            if tool_result.tool_name not in _UNDERSTANDING_TOOLS:
                continue
            last_understanding = tool_result
            if not tool_result.success or not tool_result.data:
                continue
            if tool_result.tool_name == "summarize_document":
                document_summary = DocumentsAgentDocumentSummary.model_validate(
                    tool_result.data
                )
            elif tool_result.tool_name == "ask_about_document":
                document_answer = DocumentsAgentDocumentAnswer.model_validate(
                    tool_result.data
                )

        if last_understanding is not None and not last_understanding.success:
            self._raise_from_tool_message(
                last_understanding.error or "Unable to process document"
            )

        return document_summary, document_answer

    def _raise_from_tool_message(self, message: str) -> None:
        text = (message or "").strip() or "Unable to process document"
        lowered = text.lower()
        if any(token in lowered for token in _AUTH_TOKENS):
            raise DocumentsAgentAuthorizationError(text)
        if any(token in lowered for token in _VALIDATION_TOKENS):
            raise DocumentsAgentValidationError(text)
        raise DocumentsAgentError(text)
