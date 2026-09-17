from app.modules.employees.repository import EmployeeRepository
from app.modules.onboarding.models import Onboarding, OnboardingStatus
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.service import OnboardingService
from app.tests.helpers import create_department
from app.tests.integration.test_employees import _employee_payload, _hr_headers
from app.tests.integration.test_onboarding import _hire


def _service(db_session) -> OnboardingService:
    return OnboardingService(OnboardingRepository(db_session), EmployeeRepository(db_session))


def test_backfill_creates_onboarding_for_employee_without_one(client, db_session):
    department = create_department(client)
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"], email="backfill.missing@test.com"),
        headers=_hr_headers(client, db_session),
    )
    assert created.status_code == 201, created.text
    employee_id = created.json()["id"]

    assert db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).count() == 0

    count = _service(db_session).backfill_missing_onboardings()
    assert count == 1

    onboarding = (
        db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one()
    )
    assert onboarding.status == OnboardingStatus.IN_PROGRESS
    assert onboarding.started_at is not None


def test_backfill_leaves_existing_onboarding_unchanged(client, db_session):
    _application, _job, _candidate_headers, headers, body = _hire(
        client, db_session, email="backfill.existing@test.com"
    )
    hired_employee_id = body["hired_employee_id"]
    existing = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == hired_employee_id)
        .one()
    )
    existing_id = existing.id
    existing_started_at = existing.started_at

    department = create_department(client, name="Backfill Ops")
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(
            department["id"],
            email="backfill.manual@test.com",
            first_name="Manual",
            last_name="Hire",
        ),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    manual_id = created.json()["id"]

    count = _service(db_session).backfill_missing_onboardings()
    assert count == 1

    hired_onboarding = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == hired_employee_id)
        .one()
    )
    assert hired_onboarding.id == existing_id
    assert hired_onboarding.started_at == existing_started_at

    assert (
        db_session.query(Onboarding).filter(Onboarding.employee_id == manual_id).count() == 1
    )


def test_backfill_is_idempotent(client, db_session):
    department = create_department(client)
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"], email="backfill.twice@test.com"),
        headers=_hr_headers(client, db_session),
    )
    assert created.status_code == 201, created.text
    employee_id = created.json()["id"]

    first = _service(db_session).backfill_missing_onboardings()
    assert first == 1

    second = _service(db_session).backfill_missing_onboardings()
    assert second == 0

    assert db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).count() == 1
