"""Unit tests for recruitment overview aggregation (in-memory SQLite)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.identity.models import Candidate, User
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.models import Application, ApplicationStatus, EmploymentType, Job, JobStatus
from app.modules.recruitment.repository import ApplicationRepository, JobRepository
from app.shared.exceptions import AppException
from app.tests.helpers import create_candidate_user, create_user_with_role
import pytest


def _job(db, *, title: str, created_by: int) -> Job:
    job = Job(
        title=title,
        description=f"Desc {title}",
        employment_type=EmploymentType.FULL_TIME,
        status=JobStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        created_by_user_id=created_by,
    )
    db.add(job)
    db.flush()
    return job


def _candidate(db, *, email: str) -> Candidate:
    user = create_candidate_user(
        db,
        email=email,
        password="candpass123",
        first_name=email.split("@")[0],
        last_name="Test",
    )
    return db.query(Candidate).filter(Candidate.user_id == user.id).one()


def _apply(db, *, candidate: Candidate, job: Job, status: ApplicationStatus) -> Application:
    app = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        status=status,
        submitted_at=datetime.now(UTC),
    )
    db.add(app)
    db.flush()
    return app


def _service(db) -> ApplicationService:
    # storage unused for overview methods
    return ApplicationService(db, storage=None)  # type: ignore[arg-type]


def test_overview_counts_unique_candidates_vs_applications(db_session):
    admin = create_user_with_role(
        db_session, email="admin.ov@test.com", password="adminpass123", role_name="admin"
    )
    job_a = _job(db_session, title="Java Developer", created_by=admin.id)
    job_b = _job(db_session, title="Backend Engineer", created_by=admin.id)
    c1 = _candidate(db_session, email="c1.ov@test.com")
    c2 = _candidate(db_session, email="c2.ov@test.com")
    _apply(db_session, candidate=c1, job=job_a, status=ApplicationStatus.SUBMITTED)
    _apply(db_session, candidate=c1, job=job_b, status=ApplicationStatus.SCREENING)
    _apply(db_session, candidate=c2, job=job_a, status=ApplicationStatus.SHORTLISTED)
    db_session.commit()

    overview = _service(db_session).get_recruitment_overview()
    assert overview.total_unique_candidates == 2
    assert overview.total_applications == 3
    assert overview.total_jobs_with_applications == 2
    by_title = {item.job_title: item.application_count for item in overview.applications_by_job}
    assert by_title["Java Developer"] == 2
    assert by_title["Backend Engineer"] == 1


def test_overview_filters_by_status_and_job(db_session):
    admin = create_user_with_role(
        db_session, email="admin.ov2@test.com", password="adminpass123", role_name="admin"
    )
    job = _job(db_session, title="Data Engineer", created_by=admin.id)
    other = _job(db_session, title="Other", created_by=admin.id)
    c1 = _candidate(db_session, email="c3.ov@test.com")
    _apply(db_session, candidate=c1, job=job, status=ApplicationStatus.SCREENING)
    _apply(db_session, candidate=c1, job=other, status=ApplicationStatus.REJECTED)
    db_session.commit()

    screening = _service(db_session).get_recruitment_overview(status=ApplicationStatus.SCREENING)
    assert screening.total_applications == 1
    assert screening.total_unique_candidates == 1

    for_job = _service(db_session).get_recruitment_overview(job_id=job.id)
    assert for_job.total_applications == 1
    assert for_job.applications_by_job[0].job_id == job.id


def test_list_pagination_and_empty(db_session):
    admin = create_user_with_role(
        db_session, email="admin.ov3@test.com", password="adminpass123", role_name="admin"
    )
    job = _job(db_session, title="QA", created_by=admin.id)
    c1 = _candidate(db_session, email="c4.ov@test.com")
    c2 = _candidate(db_session, email="c5.ov@test.com")
    _apply(db_session, candidate=c1, job=job, status=ApplicationStatus.SUBMITTED)
    _apply(db_session, candidate=c2, job=job, status=ApplicationStatus.SUBMITTED)
    db_session.commit()

    page = _service(db_session).list_recruitment_applications(job_id=job.id, limit=1, offset=0)
    assert page.total == 2
    assert page.limit == 1
    assert len(page.items) == 1

    empty = _service(db_session).list_recruitment_applications(
        job_id=job.id, status=ApplicationStatus.HIRED
    )
    assert empty.total == 0
    assert empty.items == []


def test_overview_unknown_job_404(db_session):
    with pytest.raises(AppException, match="Job not found"):
        _service(db_session).get_recruitment_overview(job_id=99999)
