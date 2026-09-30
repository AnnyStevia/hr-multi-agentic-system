from datetime import date, timedelta

from app.modules.identity.models import User
from app.modules.offboarding.models import OffboardingClearanceItem
from app.modules.offboarding.templates import (
    DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES,
    DEFAULT_OFFBOARDING_TASK_TEMPLATES,
)
from app.tests.helpers import (
    auth_header,
    create_candidate_user,
    create_department,
    create_user_with_role,
)
from app.tests.integration.test_organization import _create_linked_employee


def _future_day(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


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


def _admin_user_id(db_session) -> int:
    user = db_session.query(User).filter(User.email == "admin@test.com").first()
    assert user is not None
    return user.id


def test_create_seeds_default_clearance_atomically(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr Seed Dept")
    _u, emp = _emp(db_session, dept["id"], "off.clr.seed@test.com")
    case = _create_case(client, headers, emp.id)

    tasks = client.get(f"/api/v1/offboarding/{case['id']}/tasks", headers=headers)
    assert tasks.status_code == 200
    assert len(tasks.json()) == len(DEFAULT_OFFBOARDING_TASK_TEMPLATES)

    clearance = client.get(f"/api/v1/offboarding/{case['id']}/clearance", headers=headers)
    assert clearance.status_code == 200, clearance.text
    body = clearance.json()
    assert len(body) == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)
    assert all(item["status"] == "pending" for item in body)
    categories = {item["category"] for item in body}
    assert categories == {"equipment", "access"}
    labels = {item["item"] for item in body}
    assert "Laptop" in labels
    assert "Email" in labels
    assert "GitHub / repositories" in labels

    progress = client.get(
        f"/api/v1/offboarding/{case['id']}/clearance/progress", headers=headers
    )
    assert progress.status_code == 200
    prog = progress.json()
    assert prog["total"] == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)
    assert prog["pending"] == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)
    assert prog["cleared"] == 0
    assert prog["not_applicable"] == 0
    assert prog["percentage"] == 0
    assert prog["clearance_complete"] is False

    db_count = (
        db_session.query(OffboardingClearanceItem)
        .filter(OffboardingClearanceItem.offboarding_case_id == case["id"])
        .count()
    )
    assert db_count == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)


def test_no_duplicate_defaults_on_create_path(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr Dup Dept")
    _u, emp = _emp(db_session, dept["id"], "off.clr.dup@test.com")
    case = _create_case(client, headers, emp.id)
    first = client.get(f"/api/v1/offboarding/{case['id']}/clearance", headers=headers).json()
    assert len(first) == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)

    conflict = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": emp.id,
            "reason": "resignation",
            "last_working_day": _future_day(40),
        },
        headers=headers,
    )
    assert conflict.status_code == 409
    second = client.get(f"/api/v1/offboarding/{case['id']}/clearance", headers=headers).json()
    assert len(second) == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)


def test_hr_list_and_employee_self_read(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr Read Dept")
    user, emp = _emp(db_session, dept["id"], "off.clr.read@test.com")
    case = _create_case(client, headers, emp.id)

    hr_list = client.get(f"/api/v1/offboarding/{case['id']}/clearance", headers=headers)
    assert hr_list.status_code == 200
    assert len(hr_list.json()) == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)

    emp_headers = auth_header(client, "off.clr.read@test.com", "emppass123")
    mine = client.get("/api/v1/me/offboarding/clearance", headers=emp_headers)
    assert mine.status_code == 200
    body = mine.json()
    assert len(body) == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES)
    assert all(item["offboarding_case_id"] == case["id"] for item in body)
    assert "completed_by_user_id" not in body[0]

    other_user, _other = _emp(db_session, dept["id"], "off.clr.other@test.com")
    other_headers = auth_header(client, "off.clr.other@test.com", "emppass123")
    assert client.get("/api/v1/me/offboarding/clearance", headers=other_headers).json() == []
    assert user.id != other_user.id


def test_employee_and_manager_cannot_mutate(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr Mut Dept")
    _u, emp = _emp(db_session, dept["id"], "off.clr.mut@test.com")
    case = _create_case(client, headers, emp.id)
    item_id = client.get(
        f"/api/v1/offboarding/{case['id']}/clearance", headers=headers
    ).json()[0]["id"]

    emp_headers = auth_header(client, "off.clr.mut@test.com", "emppass123")
    create_user_with_role(
        db_session, email="mgr.off.clr@test.com", password="mgrpass123", role_name="manager"
    )
    mgr = auth_header(client, "mgr.off.clr@test.com", "mgrpass123")

    for blocked in (emp_headers, mgr):
        assert (
            client.post(
                f"/api/v1/offboarding/{case['id']}/clearance",
                json={"category": "equipment", "item": "Nope"},
                headers=blocked,
            ).status_code
            == 403
        )
        assert (
            client.patch(
                f"/api/v1/offboarding/{case['id']}/clearance/{item_id}",
                json={"status": "cleared"},
                headers=blocked,
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/v1/offboarding/{case['id']}/clearance", headers=blocked
            ).status_code
            == 403
        )


def test_hr_clear_na_reopen_and_completion_fields(client, db_session):
    headers = auth_header(client)
    admin_id = _admin_user_id(db_session)
    dept = create_department(client, name="Off Clr Life Dept")
    _u, emp = _emp(db_session, dept["id"], "off.clr.life@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]
    items = client.get(f"/api/v1/offboarding/{case_id}/clearance", headers=headers).json()
    item_id = items[0]["id"]

    cleared = client.patch(
        f"/api/v1/offboarding/{case_id}/clearance/{item_id}",
        json={"status": "cleared", "notes": "Returned OK"},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["status"] == "cleared"
    assert body["notes"] == "Returned OK"
    assert body["completed_at"] is not None
    assert body["completed_by_user_id"] == admin_id

    na = client.patch(
        f"/api/v1/offboarding/{case_id}/clearance/{items[1]['id']}",
        json={"status": "not_applicable"},
        headers=headers,
    )
    assert na.status_code == 200
    assert na.json()["status"] == "not_applicable"
    assert na.json()["completed_at"] is None
    assert na.json()["completed_by_user_id"] is None

    reopened = client.patch(
        f"/api/v1/offboarding/{case_id}/clearance/{item_id}",
        json={"status": "pending"},
        headers=headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "pending"
    assert reopened.json()["completed_at"] is None
    assert reopened.json()["completed_by_user_id"] is None


def test_clearance_progress_math_and_na(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr Prog Dept")
    _u, emp = _emp(db_session, dept["id"], "off.clr.prog@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]
    items = client.get(f"/api/v1/offboarding/{case_id}/clearance", headers=headers).json()
    total = len(items)
    assert total == 9

    # Mark 3 N/A and 3 cleared → required=6, cleared=3 → 50%
    for item in items[:3]:
        assert (
            client.patch(
                f"/api/v1/offboarding/{case_id}/clearance/{item['id']}",
                json={"status": "not_applicable"},
                headers=headers,
            ).status_code
            == 200
        )
    for item in items[3:6]:
        assert (
            client.patch(
                f"/api/v1/offboarding/{case_id}/clearance/{item['id']}",
                json={"status": "cleared"},
                headers=headers,
            ).status_code
            == 200
        )

    prog = client.get(
        f"/api/v1/offboarding/{case_id}/clearance/progress", headers=headers
    ).json()
    assert prog["total"] == 9
    assert prog["not_applicable"] == 3
    assert prog["cleared"] == 3
    assert prog["pending"] == 3
    assert prog["percentage"] == 50
    assert prog["clearance_complete"] is False

    for item in items[6:]:
        assert (
            client.patch(
                f"/api/v1/offboarding/{case_id}/clearance/{item['id']}",
                json={"status": "cleared"},
                headers=headers,
            ).status_code
            == 200
        )

    done = client.get(
        f"/api/v1/offboarding/{case_id}/clearance/progress", headers=headers
    ).json()
    assert done["cleared"] == 6
    assert done["percentage"] == 100
    assert done["clearance_complete"] is True


def test_all_na_is_complete_at_100(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr AllNA Dept")
    _u, emp = _emp(db_session, dept["id"], "off.clr.allna@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]
    items = client.get(f"/api/v1/offboarding/{case_id}/clearance", headers=headers).json()
    for item in items:
        assert (
            client.patch(
                f"/api/v1/offboarding/{case_id}/clearance/{item['id']}",
                json={"status": "not_applicable"},
                headers=headers,
            ).status_code
            == 200
        )
    prog = client.get(
        f"/api/v1/offboarding/{case_id}/clearance/progress", headers=headers
    ).json()
    assert prog["percentage"] == 100
    assert prog["clearance_complete"] is True
    assert prog["not_applicable"] == len(items)


def test_clearance_idor_and_custom_item(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr Idor Dept")
    _u1, emp1 = _emp(db_session, dept["id"], "off.clr.idor1@test.com")
    _u2, emp2 = _emp(db_session, dept["id"], "off.clr.idor2@test.com")
    case1 = _create_case(client, headers, emp1.id)
    case2 = _create_case(client, headers, emp2.id)
    item_id = client.get(
        f"/api/v1/offboarding/{case1['id']}/clearance", headers=headers
    ).json()[0]["id"]

    assert (
        client.patch(
            f"/api/v1/offboarding/{case2['id']}/clearance/{item_id}",
            json={"status": "cleared"},
            headers=headers,
        ).status_code
        == 404
    )

    created = client.post(
        f"/api/v1/offboarding/{case1['id']}/clearance",
        json={
            "category": "access",
            "item": "Slack workspace",
            "notes": "Custom revoke check",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    custom = created.json()
    assert custom["item"] == "Slack workspace"
    assert custom["category"] == "access"
    assert custom["status"] == "pending"
    assert custom["notes"] == "Custom revoke check"

    listed = client.get(
        f"/api/v1/offboarding/{case1['id']}/clearance", headers=headers
    ).json()
    assert len(listed) == len(DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES) + 1

    create_candidate_user(db_session, email="cand.off.clr@test.com", password="candpass123")
    cand = auth_header(client, "cand.off.clr@test.com", "candpass123")
    assert (
        client.get(
            f"/api/v1/offboarding/{case1['id']}/clearance", headers=cand
        ).status_code
        == 403
    )


def test_complete_blocked_when_clearance_incomplete(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Clr Gate Dept")
    _u, emp = _emp(db_session, dept["id"], "off.clr.gate@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]

    assert client.post(f"/api/v1/offboarding/{case_id}/start", headers=headers).status_code == 200
    assert (
        client.post(
            f"/api/v1/offboarding/{case_id}/pending-clearance", headers=headers
        ).status_code
        == 200
    )
    completed = client.post(f"/api/v1/offboarding/{case_id}/complete", headers=headers)
    assert completed.status_code == 400
    assert "Offboarding cannot be completed" in completed.json()["detail"]

    prog = client.get(
        f"/api/v1/offboarding/{case_id}/clearance/progress", headers=headers
    ).json()
    assert prog["clearance_complete"] is False
