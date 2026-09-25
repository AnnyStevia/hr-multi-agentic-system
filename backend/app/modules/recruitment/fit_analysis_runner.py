"""Background fit analysis after application submit (Phase 6.2)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.ai.agents.recruitment.exceptions import RecruitmentFitError
from app.ai.agents.recruitment.fit_service import FitAnalysisService
from app.ai.agents.recruitment.schemas import (
    FitAnswerSnapshot,
    FitCandidateSnapshot,
    FitEducationSnapshot,
    FitExperienceSnapshot,
    FitJobSnapshot,
)
from app.core.database import SessionLocal
from app.modules.recruitment.models import DocumentKind
from app.modules.recruitment.repository import ApplicationRepository
from app.shared.storage import get_storage_service
from app.shared.storage.exceptions import StorageException

logger = logging.getLogger(__name__)


def run_application_fit_analysis(application_id: int) -> None:
    """BackgroundTasks entrypoint: fresh DB session; never raises to the request path."""
    db = SessionLocal()
    try:
        _analyze_and_persist(db, application_id)
    except Exception:
        logger.exception(
            "Unhandled error in background fit analysis for application_id=%s",
            application_id,
        )
    finally:
        db.close()


def _analyze_and_persist(db, application_id: int) -> None:
    applications = ApplicationRepository(db)
    application = applications.get_by_id(application_id)
    if application is None:
        logger.warning("Fit analysis skipped: application %s not found", application_id)
        return
    if application.fit_analyzed_at is not None:
        return

    job = application.job
    questions = {q.id: q for q in job.questions}
    candidate_snapshot = FitCandidateSnapshot(
        education=[
            FitEducationSnapshot(
                institution=row.institution,
                degree=row.degree,
                field_of_study=row.field_of_study,
                start_year=row.start_year,
                end_year=row.end_year,
            )
            for row in application.education
        ],
        experience=[
            FitExperienceSnapshot(
                company=row.company,
                title=row.title,
                start_year=row.start_year,
                end_year=row.end_year,
                description=row.description,
            )
            for row in application.experience
        ],
        answers=[
            FitAnswerSnapshot(
                prompt=questions[row.question_id].prompt
                if row.question_id in questions
                else f"question_{row.question_id}",
                value=row.value,
            )
            for row in application.answers
        ],
    )
    job_snapshot = FitJobSnapshot(
        title=job.title,
        description=job.description,
        requirements=job.requirements,
        employment_type=job.employment_type.value
        if hasattr(job.employment_type, "value")
        else str(job.employment_type),
        internship_duration_months=job.internship_duration_months,
    )

    fit_service = FitAnalysisService()
    cv_text = _load_cv_text(fit_service, application)

    try:
        result = fit_service.analyze(
            job=job_snapshot,
            candidate=candidate_snapshot,
            cv_text=cv_text,
        )
    except RecruitmentFitError:
        logger.exception("Fit analysis failed for application_id=%s", application_id)
        return

    # Re-check idempotency in case of race
    db.refresh(application)
    if application.fit_analyzed_at is not None:
        return

    application.fit_score = result.fit_score
    application.fit_level = result.fit_level
    application.fit_explanation = result.explanation
    application.matching_skills = result.matching_skills
    application.missing_skills = result.missing_skills
    application.experience_match = result.experience_match
    application.education_match = result.education_match
    application.fit_analysis_version = result.analysis_version
    application.fit_analyzed_at = datetime.now(UTC)
    db.add(application)
    db.commit()


def _load_cv_text(fit_service: FitAnalysisService, application) -> str | None:
    cv_doc = next(
        (doc for doc in application.documents if doc.kind == DocumentKind.CV),
        None,
    )
    if cv_doc is None:
        return None
    try:
        storage = get_storage_service()
        content = storage.download_file(cv_doc.storage_key)
    except StorageException:
        logger.warning(
            "Could not download CV for fit analysis application_id=%s",
            application.id,
        )
        return None
    return fit_service.extract_cv_text(
        content,
        filename=cv_doc.original_filename,
        content_type=cv_doc.content_type,
    )
