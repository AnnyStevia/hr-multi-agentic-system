from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.modules.employees.repository import DepartmentRepository
from app.modules.identity.models import Candidate
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.models import Application, ApplicationStatus
from app.modules.recruitment.repository import JobRepository
from app.modules.recruitment.schemas import JobCreateRequest
from app.modules.recruitment.service import JobService
from app.shared.exceptions import AppException
from app.tests.helpers import create_candidate_user, create_user_with_role


def _application_service(db_session) -> ApplicationService:
    return ApplicationService(db_session, MagicMock())


def _create_application(db_session, status: ApplicationStatus) -> Application:
    hr = create_user_with_role(
        db_session,
        email="hr.status@test.com",
        password="hrpass123",
        role_name="hr",
    )
    job = JobService(JobRepository(db_session), DepartmentRepository(db_session)).create_job(
        JobCreateRequest(title="Analyst", description="Support HR reporting."),
        created_by_user_id=hr.id,
    )
    user = create_candidate_user(
        db_session,
        email="status.candidate@test.com",
        password="candidate123",
    )
    candidate = db_session.query(Candidate).filter(Candidate.user_id == user.id).one()
    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        status=status,
        submitted_at=datetime.now(UTC),
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


@pytest.mark.parametrize(
    "current,target",
    [
        (ApplicationStatus.SUBMITTED, ApplicationStatus.SCREENING),
        (ApplicationStatus.SUBMITTED, ApplicationStatus.REJECTED),
        (ApplicationStatus.SCREENING, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.SCREENING, ApplicationStatus.REJECTED),
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED),
    ],
)
def test_service_allows_valid_status_transitions(db_session, current, target):
    application = _create_application(db_session, current)
    updated = _application_service(db_session).update_status(application.id, target)
    assert updated.status == target


def test_service_rejects_direct_hire_status_update(db_session):
    application = _create_application(db_session, ApplicationStatus.SHORTLISTED)
    with pytest.raises(AppException) as exc:
        _application_service(db_session).update_status(application.id, ApplicationStatus.HIRED)
    assert exc.value.status_code == 400
    assert "interview outcome" in exc.value.message.lower()
    db_session.refresh(application)
    assert application.status == ApplicationStatus.SHORTLISTED


@pytest.mark.parametrize(
    "current,target",
    [
        (ApplicationStatus.SUBMITTED, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.SCREENING, ApplicationStatus.SUBMITTED),
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.SUBMITTED),
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.SCREENING),
        (ApplicationStatus.REJECTED, ApplicationStatus.SCREENING),
        (ApplicationStatus.REJECTED, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.REJECTED, ApplicationStatus.SUBMITTED),
    ],
)
def test_service_rejects_invalid_status_transitions(db_session, current, target):
    application = _create_application(db_session, current)
    with pytest.raises(AppException) as exc:
        _application_service(db_session).update_status(application.id, target)
    assert exc.value.status_code == 400
    db_session.refresh(application)
    assert application.status == current
