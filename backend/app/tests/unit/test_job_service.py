from app.modules.employees.repository import DepartmentRepository
from app.modules.recruitment.models import JobStatus
from app.modules.recruitment.repository import JobRepository
from app.modules.recruitment.schemas import JobCreateRequest
from app.modules.recruitment.service import JobService
from app.shared.exceptions import AppException
from app.tests.helpers import create_user_with_role


def _service(db_session) -> JobService:
    return JobService(JobRepository(db_session), DepartmentRepository(db_session))


def test_create_job_defaults_to_draft(db_session):
    hr = create_user_with_role(
        db_session,
        email="hr.service@test.com",
        password="hrpass123",
        role_name="hr",
    )
    job = _service(db_session).create_job(
        JobCreateRequest(title="Analyst", description="Support HR reporting."),
        created_by_user_id=hr.id,
    )
    assert job.status == JobStatus.DRAFT
    assert job.published_at is None


def test_publish_requires_draft(db_session):
    hr = create_user_with_role(
        db_session,
        email="hr.service@test.com",
        password="hrpass123",
        role_name="hr",
    )
    service = _service(db_session)
    job = service.create_job(
        JobCreateRequest(title="Analyst", description="Support HR reporting."),
        created_by_user_id=hr.id,
    )
    published = service.publish_job(job.id)
    assert published.status == JobStatus.PUBLISHED

    try:
        service.publish_job(job.id)
        raise AssertionError("Publishing a published job should fail")
    except AppException as exc:
        assert exc.status_code == 409


def test_get_published_job_hides_draft_and_closed(db_session):
    hr = create_user_with_role(
        db_session,
        email="hr.service@test.com",
        password="hrpass123",
        role_name="hr",
    )
    service = _service(db_session)
    draft = service.create_job(
        JobCreateRequest(title="Draft Role", description="Hidden from candidates."),
        created_by_user_id=hr.id,
    )
    published = service.create_job(
        JobCreateRequest(title="Published Role", description="Visible to candidates."),
        created_by_user_id=hr.id,
    )
    closed = service.create_job(
        JobCreateRequest(title="Closed Role", description="No longer open."),
        created_by_user_id=hr.id,
    )
    service.publish_job(published.id)
    service.publish_job(closed.id)
    service.close_job(closed.id)

    titles = [job.title for job in service.list_published_jobs()]
    assert titles == ["Published Role"]
    assert service.get_published_job(published.id).title == "Published Role"

    try:
        service.get_published_job(draft.id)
        raise AssertionError("Draft jobs should be hidden")
    except AppException as exc:
        assert exc.status_code == 404

    try:
        service.get_published_job(closed.id)
        raise AssertionError("Closed jobs should be hidden")
    except AppException as exc:
        assert exc.status_code == 404
