from app.modules.onboarding.models import Onboarding, OnboardingStatus
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role
from app.tests.integration.test_onboarding import _hire


def _onboarding_id(db_session, employee_id: int) -> int:
    return db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one().id


def test_hr_can_create_and_assign_training(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="train.assign@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    created = client.post(
        "/api/v1/trainings",
        json={"title": "Security Awareness", "description": "Watch the video"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    training_id = created.json()["id"]
    assert created.json()["title"] == "Security Awareness"

    assigned = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training_id},
        headers=headers,
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["status"] == "pending"
    assert assigned.json()["title"] == "Security Awareness"
    assert assigned.json()["completed_at"] is None

    listed = client.get(f"/api/v1/onboarding/{onboarding_id}/trainings", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    me_list = client.get("/api/v1/me/onboarding/trainings", headers=candidate_headers)
    assert me_list.status_code == 200
    assert len(me_list.json()) == 1
    assert me_list.json()[0]["id"] == assigned.json()["id"]


def test_duplicate_assignment_rejected(client, db_session):
    _a, _j, _cand, headers, body = _hire(client, db_session, email="train.dup@test.com")
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Compliance 101"},
        headers=headers,
    ).json()
    first = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    )
    assert second.status_code == 409


def test_employee_can_complete_own_training(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="train.complete@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Welcome Course"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    ).json()

    completed = client.patch(
        f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
        headers=candidate_headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    again = client.patch(
        f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
        headers=candidate_headers,
    )
    assert again.status_code == 400

    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.IN_PROGRESS


def test_employee_cannot_complete_another_employees_training(client, db_session):
    _a, _j, owner_headers, headers, body = _hire(
        client, db_session, email="train.owner@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Private Training"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    ).json()

    other = create_candidate_user(
        db_session, email="train.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")
    assert (
        client.patch(
            f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
            headers=other_headers,
        ).status_code
        == 404
    )
    assert owner_headers is not None


def test_hr_can_remove_assignment(client, db_session):
    _a, _j, _cand, headers, body = _hire(client, db_session, email="train.remove@test.com")
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Temp Training"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    ).json()

    deleted = client.delete(
        f"/api/v1/onboarding/{onboarding_id}/trainings/{assignment['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    listed = client.get(f"/api/v1/onboarding/{onboarding_id}/trainings", headers=headers)
    assert listed.json() == []


def test_rbac_enforced_for_training_catalog_and_assign(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="train.rbac@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    assert (
        client.post(
            "/api/v1/trainings",
            json={"title": "Nope"},
            headers=candidate_headers,
        ).status_code
        == 403
    )
    assert client.get("/api/v1/trainings", headers=candidate_headers).status_code == 403

    training = client.post(
        "/api/v1/trainings",
        json={"title": "Allowed"},
        headers=headers,
    ).json()
    assert (
        client.post(
            f"/api/v1/onboarding/{onboarding_id}/trainings",
            json={"training_id": training["id"]},
            headers=candidate_headers,
        ).status_code
        == 403
    )

    create_user_with_role(
        db_session,
        email="train.plain.emp@test.com",
        password="emppass123",
        role_name="employee",
    )
    plain = auth_header(client, email="train.plain.emp@test.com", password="emppass123")
    assert client.get("/api/v1/trainings", headers=plain).status_code == 403
