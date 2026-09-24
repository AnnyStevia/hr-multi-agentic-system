"""Unit tests for RAG document ingestion (mocked storage, no Gemini / no DB writes)."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pypdf import PdfWriter

from app.ai.rag.exceptions import (
    DocumentIngestionError,
    DocumentParseError,
    UnsupportedDocumentError,
)
from app.ai.rag.ingestion import DocumentIngestionService
from app.ai.rag.ingestion.parsers.pdf import PdfDocumentParser, _normalize_whitespace
from app.modules.documents.models import CompanyDocument, CompanyDocumentStatus
from app.shared.storage.exceptions import StorageException


def _minimal_pdf_bytes(*page_texts: str) -> bytes:
    """Build a tiny PDF with one content stream per page (Helvetica)."""

    objects: list[bytes] = []

    def add(obj: str) -> int:
        objects.append(obj.encode("latin-1"))
        return len(objects)

    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    for text in page_texts:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET"
        content_id = add(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        page_id = add(
            "<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    # Patch parent refs on pages (object numbers are 1-based in file)
    for page_id in page_ids:
        raw = objects[page_id - 1].decode("latin-1")
        objects[page_id - 1] = raw.replace("/Parent 0 0 R", f"/Parent {pages_id} 0 R").encode(
            "latin-1"
        )

    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("latin-1"))
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


def _company_document(**overrides) -> CompanyDocument:
    values = {
        "id": 42,
        "title": "Handbook",
        "description": None,
        "category_id": 1,
        "original_filename": "handbook.pdf",
        "content_type": "application/pdf",
        "size_bytes": 100,
        "storage_key": "company-documents/42/handbook.pdf",
        "version": 1,
        "uploaded_by_user_id": 1,
        "status": CompanyDocumentStatus.ACTIVE,
    }
    values.update(overrides)
    document = MagicMock(spec=CompanyDocument)
    for key, value in values.items():
        setattr(document, key, value)
    return document


def test_pdf_parser_extracts_multipage_text_and_page_numbers():
    pdf = _minimal_pdf_bytes("Page One Content", "Page Two Content")
    pages = PdfDocumentParser().parse(pdf)
    assert [p.page_number for p in pages] == [1, 2]
    assert "Page One Content" in pages[0].text
    assert "Page Two Content" in pages[1].text


def test_whitespace_normalization():
    assert _normalize_whitespace("  hello   world  \n\n\n  next  ") == "hello world\n\nnext"


def test_ingest_company_document_uses_storage_and_returns_result():
    pdf = _minimal_pdf_bytes("Alpha", "Beta")
    storage = MagicMock()
    storage.download_file.return_value = pdf
    document = _company_document()

    result = DocumentIngestionService(storage).ingest_company_document(document)  # type: ignore[arg-type]

    storage.download_file.assert_called_once_with("company-documents/42/handbook.pdf")
    assert result.company_document_id == 42
    assert result.filename == "handbook.pdf"
    assert result.content_type == "application/pdf"
    assert result.total_pages == 2
    assert "Alpha" in result.extracted_text
    assert "Beta" in result.extracted_text
    assert result.pages[0].page_number == 1
    assert result.pages[1].page_number == 2


def test_empty_pdf_bytes_raise_parse_error():
    storage = MagicMock()
    storage.download_file.return_value = b""
    with pytest.raises(DocumentParseError, match="empty"):
        DocumentIngestionService(storage).ingest_company_document(_company_document())  # type: ignore[arg-type]


def test_corrupt_pdf_raises_parse_error():
    with pytest.raises(DocumentParseError):
        PdfDocumentParser().parse(b"not-a-pdf")


def test_unsupported_document_type_rejected():
    storage = MagicMock()
    document = _company_document(
        original_filename="notes.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    with pytest.raises(UnsupportedDocumentError, match="Unsupported document type"):
        DocumentIngestionService(storage).ingest_company_document(document)  # type: ignore[arg-type]
    storage.download_file.assert_not_called()


def test_private_document_like_object_rejected():
    storage = MagicMock()
    private = SimpleNamespace(
        id=9,
        original_filename="secret.pdf",
        content_type="application/pdf",
        storage_key="private-documents/9/secret.pdf",
    )
    with pytest.raises(UnsupportedDocumentError, match="Company Document Library"):
        DocumentIngestionService(storage).ingest_company_document(private)  # type: ignore[arg-type]
    storage.download_file.assert_not_called()


def test_pending_storage_key_rejected():
    storage = MagicMock()
    document = _company_document(storage_key="pending")
    with pytest.raises(DocumentIngestionError, match="no stored object"):
        DocumentIngestionService(storage).ingest_company_document(document)  # type: ignore[arg-type]
    storage.download_file.assert_not_called()


def test_storage_failure_becomes_ingestion_error():
    storage = MagicMock()
    storage.download_file.side_effect = StorageException("Object not found", status_code=404)
    with pytest.raises(DocumentIngestionError, match="Object not found"):
        DocumentIngestionService(storage).ingest_company_document(_company_document())  # type: ignore[arg-type]


def test_blank_pdf_pages_are_preserved():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    pages = PdfDocumentParser().parse(buffer.getvalue())
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert pages[0].text == ""
    assert pages[1].text == ""
