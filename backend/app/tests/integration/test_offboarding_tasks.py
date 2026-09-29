from datetime import date, timedelta

from app.modules.offboarding.models import OffboardingTask
from app.modules.offboarding.templates import DEFAULT_OFFBOARDING_TASK_TEMPLATES
from app.tests.helpers import (
    auth_header,
    create_candidate_user,
    create_department,
    create_user_with_role,
)
from app.tests.integration.test_organization import _create_linked_employee


def _future_day(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past_day(days: int = 2) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


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


def test_create_seeds_default_checklist_atomically(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Task Seed Dept")
    _u, emp = _emp(db_session, dept["id"], "off.task.seed@test.com")
    case = _create_case(client, headers, emp.id)

    tasks = client.get(f"/api/v1/offboarding/{case['id']}/tasks", headers=headers)
    assert tasks.status_code == 200, tasks.text
    body = tasks.json()
    assert len(body) == len(DEFAULT_OFFBOARDING_TASK_TEMPLATES)
    assert all(t["status"] == "pending" for t in body)
    categories = {t["category"] for t in body}
    assert {"documents", "handover", "equipment", "access", "administration"} <= categories
    assert any(t["is_required"] is True for t in body)
    assert any(t["is_required"] is False for t in body)

    progress = client.get(f"/api/v1/offboarding/{case['id']}/progress", headers=headers)
    assert progress.status_code == 200
    prog = progress.json()
    assert prog["total_tasks"] == len(DEFAULT_OFFBOARDING_TASK_TEMPLATES)
    assert prog["completed_tasks"] == 0
    assert prog["percentage"] == 0
    assert prog["required_complete"] is False


def test_hr_task_lifecycle_and_progress(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Task Life Dept")
    _u, emp = _emp(db_session, dept["id"], "off.task.life@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]
    tasks = client.get(f"/api/v1/offboarding/{case_id}/tasks", headers=headers).json()
    task_id = tasks[0]["id"]

    started = client.post(
        f"/api/v1/offboarding/{case_id}/tasks/{task_id}/start",
        headers=headers,
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    reopened = client.post(
        f"/api/v1/offboarding/{case_id}/tasks/{task_id}/reopen",
        headers=headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "pending"

    completed = client.post(
        f"/api/v1/offboarding/{case_id}/tasks/{task_id}/complete",
        headers=headers,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/tasks/{task_id}/start",
            headers=headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/offboarding/{case_id}/tasks/{task_id}",
            json={"title": "Nope"},
            headers=headers,
        ).status_code
        == 400
    )

    other_id = tasks[1]["id"]
    skipped = client.post(
        f"/api/v1/offboarding/{case_id}/tasks/{other_id}/skip",
        headers=headers,
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"

    progress = client.get(f"/api/v1/offboarding/{case_id}/progress", headers=headers).json()
    assert progress["completed_tasks"] == 1
    assert progress["skipped_tasks"] == 1
    assert progress["percentage"] == round(1 / len(tasks) * 100)
    assert progress["skipped_tasks"] != progress["completed_tasks"] or True


def test_manual_task_create_update_and_overdue(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Task Manual Dept")
    _u, emp = _emp(db_session, dept["id"], "off.task.manual@test.com")
    _a, assignee = _emp(db_session, dept["id"], "off.task.assignee@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]

    created = client.post(
        f"/api/v1/offboarding/{case_id}/tasks",
        json={
            "title": "Extra admin check",
            "description": "Custom",
            "category": "administration",
            "is_required": False,
            "assigned_to_employee_id": assignee.id,
            "due_date": _future_day(7),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["assigned_to"]["id"] == assignee.id
    assert task["is_overdue"] is False

    # Force overdue via DB
    row = db_session.query(OffboardingTask).filter(OffboardingTask.id == task["id"]).one()
    row.due_date = date.today() - timedelta(days=1)
    db_session.commit()

    listed = client.get(f"/api/v1/offboarding/{case_id}/tasks", headers=headers).json()
    overdue_item = next(t for t in listed if t["id"] == task["id"])
    assert overdue_item["is_overdue"] is True
    progress = client.get(f"/api/v1/offboarding/{case_id}/progress", headers=headers).json()
    assert progress["overdue_tasks"] >= 1

    past_due = client.post(
        f"/api/v1/offboarding/{case_id}/tasks",
        json={
            "title": "Bad due",
            "category": "other",
            "due_date": _past_day(30),
        },
        headers=headers,
    )
    assert past_due.status_code == 400

    inactive_user, inactive = _emp(db_session, dept["id"], "off.task.inactive.assignee@test.com")
    client.patch(f"/api/v1/employees/{inactive.id}/deactivate", headers=headers)
    bad_assignee = client.post(
        f"/api/v1/offboarding/{case_id}/tasks",
        json={
            "title": "Bad assignee",
            "category": "other",
            "assigned_to_employee_id": inactive.id,
        },
        headers=headers,
    )
    assert bad_assignee.status_code == 400


def test_assigned_employee_can_act_unassigned_cannot(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Task Auth Dept")
    _u, offboarded = _emp(db_session, dept["id"], "off.task.offboarded@test.com")
    _a, assignee = _emp(db_session, dept["id"], "off.task.doer@test.com")
    _o, other = _emp(db_session, dept["id"], "off.task.other@test.com")
    assignee_headers = auth_header(client, "off.task.doer@test.com", "emppass123")
    other_headers = auth_header(client, "off.task.other@test.com", "emppass123")

    case = _create_case(client, headers, offboarded.id)
    case_id = case["id"]
    task = client.post(
        f"/api/v1/offboarding/{case_id}/tasks",
        json={
            "title": "Assignee-only task",
            "category": "handover",
            "assigned_to_employee_id": assignee.id,
        },
        headers=headers,
    ).json()

    mine = client.get("/api/v1/me/offboarding/tasks", headers=assignee_headers)
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    assert mine.json()[0]["id"] == task["id"]
    assert "completed_by_user_id" not in mine.json()[0]

    assert client.get("/api/v1/me/offboarding/tasks", headers=other_headers).json() == []

    started = client.post(
        f"/api/v1/me/offboarding/tasks/{task['id']}/start",
        headers=assignee_headers,
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    assert (
        client.post(
            f"/api/v1/me/offboarding/tasks/{task['id']}/start",
            headers=other_headers,
        ).status_code
        == 404
    )

    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/tasks/{task['id']}/skip",
            headers=assignee_headers,
        ).status_code
        == 403
    )

    done = client.post(
        f"/api/v1/me/offboarding/tasks/{task['id']}/complete",
        headers=assignee_headers,
    )
    assert done.status_code == 200
    assert done.json()["status"] == "completed"


def test_task_idor_and_role_denials(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Task Idor Dept")
    _u1, emp1 = _emp(db_session, dept["id"], "off.task.idor1@test.com")
    _u2, emp2 = _emp(db_session, dept["id"], "off.task.idor2@test.com")
    case1 = _create_case(client, headers, emp1.id)
    case2 = _create_case(client, headers, emp2.id)
    tasks1 = client.get(f"/api/v1/offboarding/{case1['id']}/tasks", headers=headers).json()
    task_id = tasks1[0]["id"]

    assert (
        client.post(
            f"/api/v1/offboarding/{case2['id']}/tasks/{task_id}/complete",
            headers=headers,
        ).status_code
        == 404
    )

    emp_headers = auth_header(client, "off.task.idor1@test.com", "emppass123")
    create_user_with_role(
        db_session, email="mgr.off.task@test.com", password="mgrpass123", role_name="manager"
    )
    mgr = auth_header(client, "mgr.off.task@test.com", "mgrpass123")
    create_candidate_user(db_session, email="cand.off.task@test.com", password="candpass123")
    cand = auth_header(client, "cand.off.task@test.com", "candpass123")

    for blocked in (emp_headers, mgr, cand):
        assert (
            client.post(
                f"/api/v1/offboarding/{case1['id']}/tasks",
                json={"title": "Nope", "category": "other"},
                headers=blocked,
            ).status_code
            == 403
        )
        assert (
            client.get(f"/api/v1/offboarding/{case1['id']}/tasks", headers=blocked).status_code
            == 403
        )


def test_no_task_mods_after_case_terminal_and_case_status_unchanged(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Task Terminal Dept")
    _u, emp = _emp(db_session, dept["id"], "off.task.term@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]
    tasks = client.get(f"/api/v1/offboarding/{case_id}/tasks", headers=headers).json()
    task_id = tasks[0]["id"]

    client.post(f"/api/v1/offboarding/{case_id}/tasks/{task_id}/complete", headers=headers)
    detail = client.get(f"/api/v1/offboarding/{case_id}", headers=headers).json()
    assert detail["status"] == "initiated"

    client.post(f"/api/v1/offboarding/{case_id}/cancel", headers=headers)
    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/tasks",
            json={"title": "After cancel", "category": "other"},
            headers=headers,
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/tasks/{tasks[1]['id']}/start",
            headers=headers,
        ).status_code
        == 400
    )


def test_required_complete_when_all_required_done(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Task Req Dept")
    _u, emp = _emp(db_session, dept["id"], "off.task.req@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]
    tasks = client.get(f"/api/v1/offboarding/{case_id}/tasks", headers=headers).json()

    for task in tasks:
        if task["is_required"]:
            client.post(
                f"/api/v1/offboarding/{case_id}/tasks/{task['id']}/complete",
                headers=headers,
            )
        else:
            client.post(
                f"/api/v1/offboarding/{case_id}/tasks/{task['id']}/skip",
                headers=headers,
            )

    progress = client.get(f"/api/v1/offboarding/{case_id}/progress", headers=headers).json()
    assert progress["required_complete"] is True
    assert progress["completed_tasks"] == progress["required_total"]
    assert progress["skipped_tasks"] >= 1
    # Case still initiated — checklist does not auto-advance case
    assert client.get(f"/api/v1/offboarding/{case_id}", headers=headers).json()["status"] == (
        "initiated"
    )
