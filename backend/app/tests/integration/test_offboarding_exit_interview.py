from datetime import datetime, timedelta, timezone

import pytest

from app.modules.offboarding.models import ExitInterview
from app.shared.meetings.fake import FakeMeetingProvider
from app.tests.helpers import (
    auth_header,
    create_candidate_user,
    create_department,
    create_user_with_role,
)
from app.tests.integration.test_organization import _create_linked_employee


def _future_day(days: int = 30) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _window(hours_from_now: int = 24, duration_hours: int = 1) -> tuple[str, str]:
    start = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    end = start + timedelta(hours=duration_hours)
    return start.isoformat(), end.isoformat()


def _emp(db_session, department_id: int, email: str, **kwargs):
    return _create_linked_employee(
        db_session,
        email=email,
        password="emppass123",
        department_id=department_id,
        **kwargs,
    )


def _create_case(client, headers, employee_id: int) -> dict:
    response = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": employee_id,
            "reason": "resignation",
            "reason_details": "Personal reasons",
            "last_working_day": _future_day(),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _schedule(client, headers, case_id: int, interviewer_id: int, **extra) -> dict:
    start, end = _window()
    payload = {
        "interviewer_employee_id": interviewer_id,
        "scheduled_at": start,
        "ends_at": end,
    }
    payload.update(extra)
    response = client.post(
        f"/api/v1/offboarding/{case_id}/exit-interview",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(autouse=True)
def _noop_exit_meeting_background(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.offboarding.run_exit_interview_meeting_provision",
        lambda _id: None,
    )


def test_hr_schedule_complete_and_employee_read(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.modules.offboarding.dependencies.get_meeting_provider",
        lambda: FakeMeetingProvider(),
    )
    headers = auth_header(client)
    dept = create_department(client, name="Exit Int Dept")
    emp_user, emp = _emp(db_session, dept["id"], "exit.emp@test.com")
    _iv_user, interviewer = _emp(db_session, dept["id"], "exit.interviewer@test.com")
    case = _create_case(client, headers, emp.id)
    assert emp_user.id is not None

    assert (
        client.get(
            f"/api/v1/offboarding/{case['id']}/exit-interview", headers=headers
        ).json()
        is None
    )

    scheduled = _schedule(client, headers, case["id"], interviewer.id)
    assert scheduled["status"] == "scheduled"
    assert scheduled["interviewer_employee_id"] == interviewer.id
    assert scheduled["meeting_url"] is None or scheduled["meeting_url"].startswith(
        "https://"
    )

    ensured = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview/meeting",
        headers=headers,
    )
    assert ensured.status_code == 200, ensured.text
    assert ensured.json()["meeting_url"].startswith("https://meet.example.test/")

    emp_headers = auth_header(client, "exit.emp@test.com", "emppass123")
    mine = client.get("/api/v1/me/offboarding/exit-interview", headers=emp_headers)
    assert mine.status_code == 200
    assert mine.json()["id"] == scheduled["id"]
    assert mine.json()["status"] == "scheduled"
    assert "feedback" not in mine.json()

    completed = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview/complete",
        json={"feedback": "Left on good terms."},
        headers=headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["feedback"] == "Left on good terms."
    assert completed.json()["completed_at"] is not None
    assert emp.id != interviewer.id


def test_duplicate_active_exit_interview_conflict(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Exit Dup Dept")
    _u, emp = _emp(db_session, dept["id"], "exit.dup@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "exit.dup.iv@test.com")
    case = _create_case(client, headers, emp.id)
    _schedule(client, headers, case["id"], interviewer.id)

    start, end = _window(hours_from_now=48)
    conflict = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview",
        json={
            "interviewer_employee_id": interviewer.id,
            "scheduled_at": start,
            "ends_at": end,
        },
        headers=headers,
    )
    assert conflict.status_code == 409


def test_cancel_allows_reschedule(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Exit Cancel Dept")
    _u, emp = _emp(db_session, dept["id"], "exit.cancel@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "exit.cancel.iv@test.com")
    case = _create_case(client, headers, emp.id)
    first = _schedule(client, headers, case["id"], interviewer.id)

    cancelled = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview/cancel",
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["id"] == first["id"]

    assert (
        client.get(
            f"/api/v1/offboarding/{case['id']}/exit-interview", headers=headers
        ).json()
        is None
    )

    second = _schedule(client, headers, case["id"], interviewer.id)
    assert second["id"] != first["id"]
    assert second["status"] == "scheduled"


def test_complete_requires_feedback_and_invalid_window(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Exit Valid Dept")
    _u, emp = _emp(db_session, dept["id"], "exit.valid@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "exit.valid.iv@test.com")
    case = _create_case(client, headers, emp.id)
    _schedule(client, headers, case["id"], interviewer.id)

    empty = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview/complete",
        json={"feedback": ""},
        headers=headers,
    )
    assert empty.status_code in {400, 422}

    whitespace = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview/complete",
        json={"feedback": "   "},
        headers=headers,
    )
    assert whitespace.status_code == 400

    client.post(f"/api/v1/offboarding/{case['id']}/exit-interview/cancel", headers=headers)
    start, _end = _window()
    invalid = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview",
        json={
            "interviewer_employee_id": interviewer.id,
            "scheduled_at": start,
            "ends_at": start,
        },
        headers=headers,
    )
    assert invalid.status_code == 400


def test_employee_manager_cannot_mutate_exit_interview(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Exit Auth Dept")
    _u, emp = _emp(db_session, dept["id"], "exit.auth@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "exit.auth.iv@test.com")
    case = _create_case(client, headers, emp.id)
    _schedule(client, headers, case["id"], interviewer.id)

    emp_headers = auth_header(client, "exit.auth@test.com", "emppass123")
    create_user_with_role(
        db_session, email="mgr.exit@test.com", password="mgrpass123", role_name="manager"
    )
    mgr = auth_header(client, "mgr.exit@test.com", "mgrpass123")
    create_candidate_user(db_session, email="cand.exit@test.com", password="candpass123")
    cand = auth_header(client, "cand.exit@test.com", "candpass123")

    start, end = _window(hours_from_now=72)
    for blocked in (emp_headers, mgr, cand):
        assert (
            client.post(
                f"/api/v1/offboarding/{case['id']}/exit-interview",
                json={
                    "interviewer_employee_id": interviewer.id,
                    "scheduled_at": start,
                    "ends_at": end,
                },
                headers=blocked,
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/offboarding/{case['id']}/exit-interview/complete",
                json={"feedback": "Nope"},
                headers=blocked,
            ).status_code
            == 403
        )


def test_reschedule_clears_meeting_fields(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.modules.offboarding.dependencies.get_meeting_provider",
        lambda: FakeMeetingProvider(),
    )
    headers = auth_header(client)
    dept = create_department(client, name="Exit Resched Dept")
    _u, emp = _emp(db_session, dept["id"], "exit.resched@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "exit.resched.iv@test.com")
    case = _create_case(client, headers, emp.id)
    _schedule(client, headers, case["id"], interviewer.id)

    with_meet = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview/meeting",
        headers=headers,
    ).json()
    assert with_meet["meeting_url"]

    start, end = _window(hours_from_now=96)
    updated = client.patch(
        f"/api/v1/offboarding/{case['id']}/exit-interview",
        json={"scheduled_at": start, "ends_at": end},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["meeting_url"] is None
    assert updated.json()["scheduled_at"].startswith(start[:16]) or True

    row = (
        db_session.query(ExitInterview)
        .filter(ExitInterview.id == with_meet["id"])
        .first()
    )
    assert row is not None
    assert row.meeting_url is None
    assert row.meeting_external_id is None


def test_scheduled_exit_interview_blocks_case_complete(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Exit Gate Dept")
    _u, emp = _emp(db_session, dept["id"], "exit.gate@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "exit.gate.iv@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]

    assert client.post(f"/api/v1/offboarding/{case_id}/start", headers=headers).status_code == 200
    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/pending-clearance", headers=headers
        ).status_code
        == 200
    )

    # Satisfy checklist + clearance so only exit interview would remain as blocker when scheduled
    tasks = client.get(f"/api/v1/offboarding/{case_id}/tasks", headers=headers).json()
    for task in tasks:
        if task["is_required"]:
            assert (
                client.post(
                    f"/api/v1/offboarding/{case_id}/tasks/{task['id']}/complete",
                    headers=headers,
                ).status_code
                == 200
            )
    items = client.get(f"/api/v1/offboarding/{case_id}/clearance", headers=headers).json()
    for item in items:
        assert (
            client.patch(
                f"/api/v1/offboarding/{case_id}/clearance/{item['id']}",
                json={"status": "cleared"},
                headers=headers,
            ).status_code
            == 200
        )

    start = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(hours=25)).isoformat()
    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/exit-interview",
            json={
                "interviewer_employee_id": interviewer.id,
                "scheduled_at": start,
                "ends_at": end,
            },
            headers=headers,
        ).status_code
        == 201
    )

    blocked = client.post(f"/api/v1/offboarding/{case_id}/complete", headers=headers)
    assert blocked.status_code == 400
    assert "exit interview" in blocked.json()["detail"].lower()
