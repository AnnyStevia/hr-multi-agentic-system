"""CV extraction: PDF text → LLM structured JSON → Pydantic (Phase 6.1)."""

from __future__ import annotations

from pydantic import ValidationError

from app.ai.agents.recruitment.exceptions import (
    RecruitmentExtractionError,
    RecruitmentExtractionUnsupportedError,
    RecruitmentExtractionValidationError,
)
from app.ai.agents.recruitment.prompts import (
    CV_EXTRACTION_JSON_SCHEMA,
    CV_EXTRACTION_SYSTEM_PROMPT,
    build_cv_extraction_user_message,
)
from app.ai.agents.recruitment.schemas import CvExtractionResult
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.core.llm.base import LLMMessage, LLMProvider
from app.ai.rag.exceptions import DocumentParseError, UnsupportedDocumentError
from app.ai.rag.ingestion.parsers.pdf import PDF_MIME, PdfDocumentParser
from app.modules.recruitment.file_validation import (
    ValidatedUpload,
    validate_application_document,
)
from app.shared.exceptions import AppException

DEFAULT_MAX_CV_CHARS = 30_000
DEFAULT_MAX_OUTPUT_TOKENS = 1500
DEFAULT_TEMPERATURE = 0.1


class CvExtractionService:
    """Extract structured candidate fields from an uploaded CV PDF.

    Does not persist results, upload to storage, or index into RAG.
    """

    def __init__(
        self,
        *,
        llm_provider: LLMProvider | None = None,
        pdf_parser: PdfDocumentParser | None = None,
        max_cv_chars: int = DEFAULT_MAX_CV_CHARS,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._llm = llm_provider if llm_provider is not None else get_llm_provider()
        self._parser = pdf_parser if pdf_parser is not None else PdfDocumentParser()
        self._max_cv_chars = max_cv_chars
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def extract_from_upload(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> CvExtractionResult:
        upload = self._validate_upload(filename, content_type, content)
        if upload.extension != ".pdf" or upload.content_type != PDF_MIME:
            raise RecruitmentExtractionUnsupportedError(
                "CV extraction currently supports PDF files only"
            )

        text = self._extract_text(upload.content, upload.filename)
        if not text.strip():
            raise RecruitmentExtractionValidationError(
                "No readable text was found in the CV"
            )

        capped = text[: self._max_cv_chars]
        return self._extract_from_text(capped)

    def extract_from_text(self, cv_text: str) -> CvExtractionResult:
        """Test/helper path: run LLM extraction on plain text."""
        cleaned = (cv_text or "").strip()
        if not cleaned:
            raise RecruitmentExtractionValidationError("CV text is empty")
        return self._extract_from_text(cleaned[: self._max_cv_chars])

    def _validate_upload(
        self,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> ValidatedUpload:
        try:
            return validate_application_document(filename, content_type, content)
        except AppException as exc:
            raise RecruitmentExtractionValidationError(exc.message) from exc

    def _extract_text(self, content: bytes, filename: str) -> str:
        if not self._parser.supports(PDF_MIME, filename):
            raise RecruitmentExtractionUnsupportedError(
                "CV extraction currently supports PDF files only"
            )
        try:
            pages = self._parser.parse(content)
        except UnsupportedDocumentError as exc:
            raise RecruitmentExtractionUnsupportedError(str(exc)) from exc
        except DocumentParseError as exc:
            raise RecruitmentExtractionValidationError(exc.message) from exc

        return "\n\n".join(page.text for page in pages if page.text).strip()

    def _extract_from_text(self, cv_text: str) -> CvExtractionResult:
        messages = [
            LLMMessage(role="system", content=CV_EXTRACTION_SYSTEM_PROMPT),
            LLMMessage(role="user", content=build_cv_extraction_user_message(cv_text)),
        ]
        try:
            response = self._llm.generate_structured(
                messages,
                schema=CV_EXTRACTION_JSON_SCHEMA,
                temperature=self._temperature,
                max_tokens=self._max_output_tokens,
            )
        except LLMConfigurationError as exc:
            raise RecruitmentExtractionError(
                "CV extraction is not configured"
            ) from exc
        except LLMProviderError as exc:
            raise RecruitmentExtractionError(
                "CV extraction failed. Please try again or fill the form manually."
            ) from exc

        try:
            return CvExtractionResult.model_validate(response.data)
        except ValidationError as exc:
            raise RecruitmentExtractionValidationError(
                "CV extraction returned invalid structured data"
            ) from exc
