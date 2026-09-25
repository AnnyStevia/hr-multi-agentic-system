"""Integration tests for application fit analysis (mocked LLM)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.ai.agents.recruitment.fit_service import FitAnalysisService
from app.ai.agents.recruitment.schemas import FitAnalysisResult
from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm.base import LLMStructuredResponse, LLMUsage
from app.modules.recruitment.fit_analysis_runner import run_application_fit_analysis
from app.modules.recruitment.models import Application
from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_applications import (
    QUESTIONS,
    _apply_form,
    _candidate_headers,
    _create_published_job,
    _job_payload,
    _mock_storage,
    _use_storage,
)
from app.tests.unit.test_fit_analysis import _llm_payload


def _session_factory(db_session):
    """Return the test session without closing it (TestClient owns the session)."""

    def factory():
        db_session.close = lambda: None  # type: ignore[method-assign]
        return db_session

    return factory


def _submit(client, db_session, *, email="fit.cand@test.com", job=None):
    storage = _mock_storage()
    storage.download_file.return_value = b"%PDF-1.4\n%%EOF"
    _use_storage(client, storage)
    published = job or _create_published_job(client)
    headers = _candidate_headers(client, db_session, email=email)
    data, files = _apply_form(published)
    response = client.post(
        f"/api/v1/careers/jobs/{published['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json(), published, headers, storage


def test_apply_response_has_no_fit_fields(client, db_session):
    body, _job, _headers, _storage = _submit(client, db_session)
    assert "fit_assessment" not in body
    assert "fit_score" not in body


def test_candidate_own_application_has_no_fit_assessment(client, db_session):
    body, _job, headers, _storage = _submit(client, db_session, email="fit.own@test.com")
    own = client.get(f"/api/v1/careers/applications/{body['id']}", headers=headers)
    assert own.status_code == 200
    assert "fit_assessment" not in own.json()


def test_hr_sees_fit_assessment_when_present(client, db_session):
    body, _job, _cand, _storage = _submit(client, db_session, email="fit.hrview@test.com")
    application = db_session.query(Application).filter(Application.id == body["id"]).one()
    application.fit_score = 82
    application.fit_level = "GOOD"
    application.fit_explanation = "Strong Python and FastAPI match."
    application.matching_skills = ["Python", "FastAPI"]
    application.missing_skills = ["Kubernetes"]
    application.experience_match = "Strong match"
    application.education_match = "Match"
    application.fit_analysis_version = "1"
    application.fit_analyzed_at = datetime.now(UTC)
    db_session.commit()

    create_user_with_role(db_session, email="fit.hr@test.com", password="hrpass123", role_name="hr")
    hr = auth_header(client, "fit.hr@test.com", "hrpass123")
    response = client.get(f"/api/v1/applications/{body['id']}", headers=hr)
    assert response.status_code == 200
    fit = response.json()["fit_assessment"]
    assert fit["fit_score"] == 82
    assert fit["fit_level"] == "GOOD"
    assert fit["matching_skills"] == ["Python", "FastAPI"]
    assert fit["missing_skills"] == ["Kubernetes"]


def test_hr_list_includes_fit_score(client, db_session):
    body, job, _cand, _storage = _submit(client, db_session, email="fit.list@test.com")
    application = db_session.query(Application).filter(Application.id == body["id"]).one()
    application.fit_score = 55
    application.fit_level = "MEDIUM"
    application.fit_analyzed_at = datetime.now(UTC)
    db_session.commit()

    listed = client.get(
        f"/api/v1/jobs/{job['id']}/applications",
        headers=auth_header(client),
    )
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == body["id"])
    assert row["fit_score"] == 55
    assert row["fit_level"] == "MEDIUM"


def test_background_runner_persists_independent_analyses(client, db_session, monkeypatch):
    storage = _mock_storage()
    storage.download_file.return_value = b"%PDF-1.4\n%%EOF"
    _use_storage(client, storage)

    job_a = _create_published_job(client)
    payload_b = _job_payload(client)
    payload_b["title"] = "Data Engineer"
    payload_b["description"] = "SQL and ETL."
    payload_b["questions"] = QUESTIONS
    job_b = _create_published_job(client, payload=payload_b)

    headers = _candidate_headers(client, db_session, email="fit.multi@test.com")
    for job in (job_a, job_b):
        data, files = _apply_form(job)
        created = client.post(
            f"/api/v1/careers/jobs/{job['id']}/applications",
            data=data,
            files=files,
            headers=headers,
        )
        assert created.status_code == 201, created.text

    apps = db_session.query(Application).order_by(Application.id).all()
    assert len(apps) == 2

    scores = [88, 40]
    call_idx = {"n": 0}

    def fake_analyze(self, *, job, candidate, cv_text=None):
        i = call_idx["n"]
        call_idx["n"] += 1
        score = scores[i]
        return FitAnalysisResult(
            fit_score=score,
            fit_level="GOOD" if score >= 75 else "BAD",
            matching_skills=["Python"] if score >= 75 else [],
            missing_skills=[] if score >= 75 else ["SQL"],
            experience_match="ok",
            education_match="ok",
            explanation=f"Independent analysis score={score}",
            analysis_version="1",
        )

    monkeypatch.setattr(FitAnalysisService, "analyze", fake_analyze)
    monkeypatch.setattr(FitAnalysisService, "extract_cv_text", lambda self, *a, **k: None)
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.SessionLocal",
        _session_factory(db_session),
    )
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.get_storage_service",
        lambda: storage,
    )

    run_application_fit_analysis(apps[0].id)
    run_application_fit_analysis(apps[1].id)

    db_session.expire_all()
    apps = db_session.query(Application).order_by(Application.id).all()
    assert apps[0].fit_score == 88
    assert apps[0].fit_level == "GOOD"
    assert apps[1].fit_score == 40
    assert apps[1].fit_level == "BAD"
    assert apps[0].fit_explanation != apps[1].fit_explanation


def test_runner_skips_when_already_analyzed(client, db_session, monkeypatch):
    body, _job, _h, storage = _submit(client, db_session, email="fit.skip@test.com")
    application = db_session.query(Application).filter(Application.id == body["id"]).one()
    application.fit_score = 70
    application.fit_level = "MEDIUM"
    application.fit_analyzed_at = datetime.now(UTC)
    db_session.commit()

    analyze = MagicMock()
    monkeypatch.setattr(FitAnalysisService, "analyze", analyze)
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.SessionLocal",
        _session_factory(db_session),
    )
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.get_storage_service",
        lambda: storage,
    )
    run_application_fit_analysis(application.id)
    analyze.assert_not_called()


def test_runner_llm_failure_leaves_application_valid(client, db_session, monkeypatch):
    body, _job, _h, storage = _submit(client, db_session, email="fit.fail@test.com")
    application = db_session.query(Application).filter(Application.id == body["id"]).one()

    llm = MagicMock()
    llm.generate_structured.side_effect = LLMProviderError("no credits")
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.FitAnalysisService",
        lambda: FitAnalysisService(llm_provider=llm),
    )
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.SessionLocal",
        _session_factory(db_session),
    )
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.get_storage_service",
        lambda: storage,
    )

    run_application_fit_analysis(application.id)
    db_session.refresh(application)
    assert application.status.value == "submitted"
    assert application.fit_analyzed_at is None
    assert application.fit_score is None


def test_apply_schedules_background_fit_task(client, db_session, monkeypatch):
    calls: list[int] = []

    def capture(application_id: int) -> None:
        calls.append(application_id)

    monkeypatch.setattr("app.api.v1.careers.run_application_fit_analysis", capture)
    body, _job, _h, _s = _submit(client, db_session, email="fit.sched@test.com")
    assert calls == [body["id"]]


def test_runner_persists_from_mocked_llm(client, db_session, monkeypatch):
    body, _job, _h, storage = _submit(client, db_session, email="fit.persist@test.com")
    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data=_llm_payload(fit_score=82),
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.FitAnalysisService",
        lambda: FitAnalysisService(llm_provider=llm),
    )
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.SessionLocal",
        _session_factory(db_session),
    )
    monkeypatch.setattr(
        "app.modules.recruitment.fit_analysis_runner.get_storage_service",
        lambda: storage,
    )
    monkeypatch.setattr(
        FitAnalysisService,
        "extract_cv_text",
        lambda self, *a, **k: "Python FastAPI",
    )

    run_application_fit_analysis(body["id"])
    application = db_session.query(Application).filter(Application.id == body["id"]).one()
    assert application.fit_score == 82
    assert application.fit_level == "GOOD"
    assert application.matching_skills == ["Python", "FastAPI", "PostgreSQL"]
    assert application.fit_analyzed_at is not None
