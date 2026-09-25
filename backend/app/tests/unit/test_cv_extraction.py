"""Unit tests for Recruitment AI CV extraction (mocked LLM; no Gemini credits)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ai.agents.recruitment import (
    CvExtractionService,
    RecruitmentExtractionError,
    RecruitmentExtractionUnsupportedError,
    RecruitmentExtractionValidationError,
)
from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm.base import LLMStructuredResponse, LLMUsage
from app.ai.rag.ingestion.parsers.pdf import PdfDocumentParser


def _minimal_pdf_bytes(*page_texts: str) -> bytes:
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
    for i, pid in enumerate(page_ids):
        objects[pid - 1] = objects[pid - 1].replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode())
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


SAMPLE_EXTRACTION = {
    "full_name": "Ada Lovelace",
    "email": "ada@example.com",
    "phone": "+216 20 111 222",
    "location": "Tunis",
    "education": [
        {
            "institution": "INSAT",
            "degree": "Engineering",
            "field_of_study": "Software",
            "start_year": 2020,
            "end_year": 2025,
        },
        {
            "institution": "High School",
            "degree": None,
            "field_of_study": None,
            "start_year": 2017,
            "end_year": 2020,
        },
    ],
    "experience": [
        {
            "company": "Acme",
            "title": "Intern",
            "start_year": 2024,
            "end_year": 2024,
            "description": "Backend APIs",
        },
        {
            "company": "Beta",
            "title": "Developer",
            "start_year": 2025,
            "end_year": None,
            "description": None,
        },
    ],
    "skills": ["Python", "FastAPI"],
    "languages": ["English", "French"],
    "certifications": ["AWS CAP"],
    "projects": ["HR platform"],
}


def _llm_ok(data: dict | None = None) -> MagicMock:
    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data=data if data is not None else SAMPLE_EXTRACTION,
        model="gemini-mock",
        usage=LLMUsage(input_tokens=10, output_tokens=20, total_tokens=30),
    )
    return llm


def test_valid_cv_text_to_structured_extraction():
    service = CvExtractionService(llm_provider=_llm_ok())
    result = service.extract_from_text("Ada Lovelace\nPython developer")
    assert result.full_name == "Ada Lovelace"
    assert result.email == "ada@example.com"
    assert len(result.education) == 2
    assert len(result.experience) == 2
    assert result.skills == ["Python", "FastAPI"]
    assert result.languages == ["English", "French"]


def test_missing_optional_fields_become_null_or_empty():
    llm = _llm_ok(
        {
            "full_name": None,
            "email": None,
            "phone": None,
            "location": None,
            "education": [],
            "experience": [],
            "skills": [],
            "languages": [],
            "certifications": [],
            "projects": [],
        }
    )
    result = CvExtractionService(llm_provider=llm).extract_from_text("Sparse CV")
    assert result.full_name is None
    assert result.education == []
    assert result.skills == []


def test_multiple_work_and_education_entries():
    result = CvExtractionService(llm_provider=_llm_ok()).extract_from_text("CV")
    assert result.education[0].institution == "INSAT"
    assert result.education[1].institution == "High School"
    assert result.experience[0].title == "Intern"
    assert result.experience[1].company == "Beta"


def test_skills_and_languages_extraction():
    result = CvExtractionService(llm_provider=_llm_ok()).extract_from_text("CV")
    assert "Python" in result.skills
    assert "French" in result.languages


def test_invalid_structured_llm_output_raises_validation_error():
    llm = _llm_ok({"full_name": "Only"})  # missing required schema fields for Pydantic defaults ok
    # Actually CvExtractionResult has defaults for lists - full_name alone is valid.
    # Force invalid year:
    llm = _llm_ok(
        {
            **SAMPLE_EXTRACTION,
            "education": [
                {
                    "institution": "X",
                    "degree": None,
                    "field_of_study": None,
                    "start_year": 1800,
                    "end_year": None,
                }
            ],
        }
    )
    with pytest.raises(RecruitmentExtractionValidationError):
        CvExtractionService(llm_provider=llm).extract_from_text("CV")


def test_empty_cv_text_raises():
    with pytest.raises(RecruitmentExtractionValidationError, match="empty"):
        CvExtractionService(llm_provider=_llm_ok()).extract_from_text("   ")


def test_empty_pdf_text_raises_after_parse():
    llm = _llm_ok()
    parser = MagicMock(spec=PdfDocumentParser)
    parser.supports.return_value = True
    page = MagicMock()
    page.text = "   "
    parser.parse.return_value = [page]
    service = CvExtractionService(llm_provider=llm, pdf_parser=parser)
    with pytest.raises(RecruitmentExtractionValidationError, match="No readable text"):
        service.extract_from_upload(
            filename="cv.pdf",
            content_type="application/pdf",
            content=_minimal_pdf_bytes("ignored"),
        )
    llm.generate_structured.assert_not_called()


def test_unsupported_docx_raises():
    docx = b"PK\x03\x04" + b"x" * 40
    with pytest.raises(RecruitmentExtractionUnsupportedError, match="PDF"):
        CvExtractionService(llm_provider=_llm_ok()).extract_from_upload(
            filename="cv.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=docx,
        )


def test_provider_failure_maps_to_extraction_error():
    llm = MagicMock()
    llm.generate_structured.side_effect = LLMProviderError("quota")
    with pytest.raises(RecruitmentExtractionError, match="failed"):
        CvExtractionService(llm_provider=llm).extract_from_text("Some CV text")


def test_pdf_upload_path_calls_llm_and_not_rag_indexing():
    llm = _llm_ok()
    service = CvExtractionService(llm_provider=llm)
    with patch("app.ai.rag.indexing.service.CompanyDocumentIndexingService") as indexing:
        result = service.extract_from_upload(
            filename="cv.pdf",
            content_type="application/pdf",
            content=_minimal_pdf_bytes("Jane Candidate Python"),
        )
        indexing.assert_not_called()
    assert result.full_name == "Ada Lovelace"
    llm.generate_structured.assert_called_once()
    call_kwargs = llm.generate_structured.call_args
    assert call_kwargs.kwargs["max_tokens"] == 1500
    assert call_kwargs.kwargs["temperature"] == 0.1
