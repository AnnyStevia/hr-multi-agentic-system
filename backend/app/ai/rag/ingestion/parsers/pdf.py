"""PDF text extraction via pypdf."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ai.rag.exceptions import DocumentParseError
from app.ai.rag.ingestion.parsers.base import DocumentParser
from app.ai.rag.ingestion.schemas import IngestedPage

PDF_MIME = "application/pdf"
_SPACES = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


class PdfDocumentParser(DocumentParser):
    def supports(self, content_type: str | None, filename: str | None) -> bool:
        mime = (content_type or "").strip().lower()
        if mime == PDF_MIME or mime.startswith("application/pdf;"):
            return True
        if filename:
            return PurePosixPath(filename).suffix.lower() == ".pdf"
        return False

    def parse(self, file_bytes: bytes) -> list[IngestedPage]:
        if not file_bytes:
            raise DocumentParseError("PDF file is empty")

        try:
            reader = PdfReader(BytesIO(file_bytes), strict=False)
        except PdfReadError as exc:
            raise DocumentParseError("Invalid or corrupted PDF") from exc
        except Exception as exc:
            raise DocumentParseError("Failed to read PDF") from exc

        if getattr(reader, "is_encrypted", False):
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise DocumentParseError("Encrypted PDF cannot be opened") from exc
            if unlocked == 0:
                raise DocumentParseError("Encrypted PDF cannot be opened")

        pages: list[IngestedPage] = []
        try:
            for index, page in enumerate(reader.pages):
                raw = page.extract_text() or ""
                pages.append(
                    IngestedPage(
                        page_number=index + 1,
                        text=_normalize_whitespace(raw),
                    )
                )
        except DocumentParseError:
            raise
        except Exception as exc:
            raise DocumentParseError("Failed to extract text from PDF") from exc

        if not pages:
            raise DocumentParseError("PDF has no pages")

        return pages


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = _BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()
