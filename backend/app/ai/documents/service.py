"""Document Understanding service: summarize + grounded Q&A on one authorized PDF."""

from __future__ import annotations

from pydantic import ValidationError

from app.ai.core.context.models import AIExecutionContext
from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.core.llm.base import LLMMessage, LLMProvider
from app.ai.documents.access import AuthorizedDocumentAccess
from app.ai.documents.context import build_document_context
from app.ai.documents.citations import sanitize_citations
from app.ai.documents.exceptions import (
    DocumentUnderstandingLLMError,
    DocumentUnderstandingValidationError,
)
from app.ai.documents.parser import DocumentUnderstandingParser
from app.ai.documents.prompts import (
    DOCUMENT_ABSTENTION,
    QA_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_qa_user_message,
    build_summary_user_message,
)
from app.ai.documents.schemas import (
    ANSWER_JSON_SCHEMA,
    SUMMARY_JSON_SCHEMA,
    DocumentAnswer,
    DocumentRef,
    DocumentSummary,
)
from app.ai.documents.settings import (
    DocumentUnderstandingSettings,
    document_understanding_settings,
)


class DocumentUnderstandingService:
    """Authorize → parse → structured LLM summarize / Q&A. No agent, no HTTP."""

    def __init__(
        self,
        access: AuthorizedDocumentAccess,
        *,
        llm_provider: LLMProvider | None = None,
        parser: DocumentUnderstandingParser | None = None,
        settings: DocumentUnderstandingSettings | None = None,
    ) -> None:
        self._access = access
        self._llm = llm_provider if llm_provider is not None else get_llm_provider()
        self._parser = parser or DocumentUnderstandingParser(settings=settings)
        self._settings = settings or document_understanding_settings

    def summarize_document(
        self, ref: DocumentRef, context: AIExecutionContext
    ) -> DocumentSummary:
        payload, source_type = self._access.resolve(ref, context)
        doc_context = build_document_context(
            payload, source_type, parser=self._parser
        )
        messages = [
            LLMMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
            LLMMessage(role="user", content=build_summary_user_message(doc_context)),
        ]
        data, model = self._call_structured(messages, SUMMARY_JSON_SCHEMA)
        try:
            summary = DocumentSummary.model_validate(data)
        except ValidationError as exc:
            raise DocumentUnderstandingValidationError(
                "Model returned an invalid summary"
            ) from exc
        summary.document_id = doc_context.document_id
        summary.source_type = source_type
        summary.truncated = doc_context.truncated
        summary.model = model
        return summary

    def answer_question_about_document(
        self,
        ref: DocumentRef,
        question: str,
        context: AIExecutionContext,
    ) -> DocumentAnswer:
        cleaned_question = (question or "").strip()
        if not cleaned_question:
            raise DocumentUnderstandingValidationError("Question must not be empty")

        payload, source_type = self._access.resolve(ref, context)
        doc_context = build_document_context(
            payload, source_type, parser=self._parser
        )
        messages = [
            LLMMessage(role="system", content=QA_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_qa_user_message(cleaned_question, doc_context),
            ),
        ]
        data, model = self._call_structured(messages, ANSWER_JSON_SCHEMA)
        raw_answer = data.get("answer") if isinstance(data, dict) else None
        if not isinstance(raw_answer, str) or not raw_answer.strip():
            raise DocumentUnderstandingValidationError(
                "Model returned an empty answer"
            )

        answer_text = raw_answer.strip()
        citations = sanitize_citations(
            data.get("citations") if isinstance(data, dict) else None,
            doc_context,
            settings=self._settings,
        )

        # Deterministic abstention when the model cannot ground an answer.
        if answer_text == DOCUMENT_ABSTENTION or _looks_like_abstention(answer_text):
            return DocumentAnswer(
                answer=DOCUMENT_ABSTENTION,
                citations=[],
                document_id=doc_context.document_id,
                source_type=source_type,
                truncated=doc_context.truncated,
                has_context=bool(doc_context.pages),
                model=model,
            )

        return DocumentAnswer(
            answer=answer_text,
            citations=citations,
            document_id=doc_context.document_id,
            source_type=source_type,
            truncated=doc_context.truncated,
            has_context=True,
            model=model,
        )

    def _call_structured(
        self, messages: list[LLMMessage], schema: dict
    ) -> tuple[dict, str]:
        try:
            response = self._llm.generate_structured(
                messages,
                schema=schema,
                temperature=self._settings.doc_understanding_temperature,
                max_tokens=self._settings.doc_understanding_max_output_tokens,
            )
        except LLMProviderError as exc:
            raise DocumentUnderstandingLLMError(
                "Document understanding generation failed"
            ) from exc
        data = response.data if isinstance(response.data, dict) else {}
        return data, response.model or ""


def _looks_like_abstention(answer: str) -> bool:
    lowered = answer.lower()
    return (
        "couldn't find enough information" in lowered
        or "could not find enough information" in lowered
        or "not enough information in this document" in lowered
    )
