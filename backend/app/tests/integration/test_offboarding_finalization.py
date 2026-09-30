from datetime import date, datetime, timedelta, timezone

from app.tests.helpers import auth_header, create_department
from app.tests.integration.test_organization import _create_linked_employee


def _future_day(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


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


def _create_case(client, headers, employee_id: int, **extra) -> dict:
    payload = {
        "employee_id": employee_id,
        "reason": "resignation",
        "reason_details": "Personal reasons",
        "last_working_day": _future_day(),
    }
    payload.update(extra)
    response = client.post("/api/v1/offboarding", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _to_pending_clearance(client, headers, case_id: int) -> None:
    assert client.post(f"/api/v1/offboarding/{case_id}/start", headers=headers).status_code == 200
    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/pending-clearance", headers=headers
        ).status_code
        == 200
    )


def _complete_required_tasks(client, headers, case_id: int) -> None:
    tasks = client.get(f"/api/v1/offboarding/{case_id}/tasks", headers=headers).json()
    for task in tasks:
        if not task["is_required"]:
            continue
        if task["status"] == "completed":
            continue
        done = client.post(
            f"/api/v1/offboarding/{case_id}/tasks/{task['id']}/complete",
            headers=headers,
        )
        assert done.status_code == 200, done.text


def _clear_all_clearance(client, headers, case_id: int, *, as_na: bool = False) -> None:
    status = "not_applicable" if as_na else "cleared"
    items = client.get(f"/api/v1/offboarding/{case_id}/clearance", headers=headers).json()
    for item in items:
        if item["status"] == status:
            continue
        patched = client.patch(
            f"/api/v1/offboarding/{case_id}/clearance/{item['id']}",
            json={"status": status},
            headers=headers,
        )
        assert patched.status_code == 200, patched.text


def _prepare_ready_case(client, headers, employee_id: int) -> dict:
    case = _create_case(client, headers, employee_id)
    _to_pending_clearance(client, headers, case["id"])
    _complete_required_tasks(client, headers, case["id"])
    _clear_all_clearance(client, headers, case["id"])
    return case


def test_incomplete_checklist_blocks_completion(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Checklist Block")
    _u, emp = _emp(db_session, dept["id"], "fin.chk.block@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])
    _clear_all_clearance(client, headers, case["id"])

    blocked = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert blocked.status_code == 400
    assert "checklist" in blocked.json()["detail"].lower()

    readiness = client.get(
        f"/api/v1/offboarding/{case['id']}/can-complete", headers=headers
    )
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["can_complete"] is False
    assert any("checklist" in b for b in body["blockers"])


def test_required_checklist_done_satisfies_checklist_rule(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Checklist Ok")
    _u, emp = _emp(db_session, dept["id"], "fin.chk.ok@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])
    _complete_required_tasks(client, headers, case["id"])

    readiness = client.get(
        f"/api/v1/offboarding/{case['id']}/can-complete", headers=headers
    ).json()
    assert not any("checklist" in b for b in readiness["blockers"])
    assert readiness["can_complete"] is False  # clearance still pending


def test_pending_clearance_blocks_completion(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Clr Pending")
    _u, emp = _emp(db_session, dept["id"], "fin.clr.pend@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])
    _complete_required_tasks(client, headers, case["id"])

    blocked = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert blocked.status_code == 400
    assert "clearance" in blocked.json()["detail"].lower()


def test_na_clearance_does_not_block(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Clr NA")
    _u, emp = _emp(db_session, dept["id"], "fin.clr.na@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])
    _complete_required_tasks(client, headers, case["id"])
    _clear_all_clearance(client, headers, case["id"], as_na=True)

    readiness = client.get(
        f"/api/v1/offboarding/{case['id']}/can-complete", headers=headers
    ).json()
    assert not any("clearance" in b for b in readiness["blockers"])
    assert readiness["can_complete"] is True

    done = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"


def test_incomplete_clearance_blocks(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Clr Incomplete")
    _u, emp = _emp(db_session, dept["id"], "fin.clr.inc@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])
    _complete_required_tasks(client, headers, case["id"])
    items = client.get(
        f"/api/v1/offboarding/{case['id']}/clearance", headers=headers
    ).json()
    # Clear all but one
    for item in items[:-1]:
        assert (
            client.patch(
                f"/api/v1/offboarding/{case['id']}/clearance/{item['id']}",
                json={"status": "cleared"},
                headers=headers,
            ).status_code
            == 200
        )

    blocked = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert blocked.status_code == 400
    assert "clearance" in blocked.json()["detail"].lower()


def test_scheduled_exit_interview_blocks(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Exit Sched")
    _u, emp = _emp(db_session, dept["id"], "fin.exit.sched@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "fin.exit.sched.iv@test.com")
    case = _prepare_ready_case(client, headers, emp.id)
    start, end = _window()
    created = client.post(
        f"/api/v1/offboarding/{case['id']}/exit-interview",
        json={
            "interviewer_employee_id": interviewer.id,
            "scheduled_at": start,
            "ends_at": end,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text

    blocked = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert blocked.status_code == 400
    assert "exit interview" in blocked.json()["detail"].lower()


def test_completed_exit_interview_allows_completion(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Exit Done")
    _u, emp = _emp(db_session, dept["id"], "fin.exit.done@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "fin.exit.done.iv@test.com")
    case = _prepare_ready_case(client, headers, emp.id)
    start, end = _window()
    assert (
        client.post(
            f"/api/v1/offboarding/{case['id']}/exit-interview",
            json={
                "interviewer_employee_id": interviewer.id,
                "scheduled_at": start,
                "ends_at": end,
            },
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/offboarding/{case['id']}/exit-interview/complete",
            json={"feedback": "Wrap-up complete."},
            headers=headers,
        ).status_code
        == 200
    )

    done = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"


def test_cancelled_exit_interview_does_not_block(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Exit Cancel")
    _u, emp = _emp(db_session, dept["id"], "fin.exit.cancel@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "fin.exit.cancel.iv@test.com")
    case = _prepare_ready_case(client, headers, emp.id)
    start, end = _window()
    assert (
        client.post(
            f"/api/v1/offboarding/{case['id']}/exit-interview",
            json={
                "interviewer_employee_id": interviewer.id,
                "scheduled_at": start,
                "ends_at": end,
            },
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/offboarding/{case['id']}/exit-interview/cancel",
            headers=headers,
        ).status_code
        == 200
    )

    done = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"


def test_no_exit_interview_does_not_block(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Exit None")
    _u, emp = _emp(db_session, dept["id"], "fin.exit.none@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    readiness = client.get(
        f"/api/v1/offboarding/{case['id']}/can-complete", headers=headers
    ).json()
    assert readiness["can_complete"] is True
    assert readiness["blockers"] == []

    done = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"


def test_successful_completion_and_repeat_safe(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Success")
    _u, emp = _emp(db_session, dept["id"], "fin.success@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    done = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"
    assert done.json()["completed_at"] is not None

    again = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert again.status_code == 400
    assert "completed" in again.json()["detail"].lower()


def test_cancel_unchanged_from_pending_clearance(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Cancel")
    _u, emp = _emp(db_session, dept["id"], "fin.cancel@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])

    cancelled = client.post(f"/api/v1/offboarding/{case['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_multiple_blockers_combined_message(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Fin Multi")
    _u, emp = _emp(db_session, dept["id"], "fin.multi@test.com")
    _iv, interviewer = _emp(db_session, dept["id"], "fin.multi.iv@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])
    start, end = _window()
    assert (
        client.post(
            f"/api/v1/offboarding/{case['id']}/exit-interview",
            json={
                "interviewer_employee_id": interviewer.id,
                "scheduled_at": start,
                "ends_at": end,
            },
            headers=headers,
        ).status_code
        == 201
    )

    blocked = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert blocked.status_code == 400
    detail = blocked.json()["detail"]
    assert detail.startswith("Offboarding cannot be completed:")
    assert "checklist" in detail.lower()
    assert "clearance" in detail.lower()
    assert "exit interview" in detail.lower()
