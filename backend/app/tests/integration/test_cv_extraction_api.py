"""API tests for CV extraction endpoint (mocked LLM; no Gemini)."""

from unittest.mock import MagicMock

from app.ai.agents.recruitment.service import CvExtractionService
from app.ai.core.llm.base import LLMStructuredResponse, LLMUsage
from app.api.v1.career_applications import get_cv_extraction_service
from app.modules.identity.models import Candidate
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role
from app.tests.unit.test_cv_extraction import SAMPLE_EXTRACTION, _minimal_pdf_bytes


def _override_extraction(client, llm: MagicMock) -> None:
    service = CvExtractionService(llm_provider=llm)
    client.app.dependency_overrides[get_cv_extraction_service] = lambda: service


def test_extract_requires_auth(client):
    response = client.post(
        "/api/v1/careers/cv/extract",
        files={"cv": ("cv.pdf", _minimal_pdf_bytes("Ada"), "application/pdf")},
    )
    assert response.status_code == 401


def test_employee_cannot_extract_cv(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.cvextract@test.com",
        password="emppass123",
        role_name="employee",
    )
    headers = auth_header(client, "emp.cvextract@test.com", "emppass123")
    response = client.post(
        "/api/v1/careers/cv/extract",
        files={"cv": ("cv.pdf", _minimal_pdf_bytes("Ada"), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 403


def test_candidate_extract_returns_structured_json_without_db_write(client, db_session):
    user = create_candidate_user(
        db_session, email="cand.cvextract@test.com", password="candpass123"
    )
    candidate = db_session.query(Candidate).filter(Candidate.user_id == user.id).one()
    phone_before = candidate.phone

    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data=SAMPLE_EXTRACTION,
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    _override_extraction(client, llm)

    headers = auth_header(client, "cand.cvextract@test.com", "candpass123")
    response = client.post(
        "/api/v1/careers/cv/extract",
        files={"cv": ("cv.pdf", _minimal_pdf_bytes("Ada Lovelace Python"), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["extraction"]["full_name"] == "Ada Lovelace"
    assert body["extraction"]["skills"] == ["Python", "FastAPI"]
    assert len(body["extraction"]["education"]) == 2

    db_session.refresh(candidate)
    assert candidate.phone == phone_before
