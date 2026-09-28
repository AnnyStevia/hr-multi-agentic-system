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
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "completed"

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
    assert (
        client.patch(
            f"/api/v1/trainings/{training['id']}",
            json={"resource_url": "https://learn.example.com/x"},
            headers=plain,
        ).status_code
        == 403
    )


def test_creating_training_notifies_all_active_employees(client, db_session):
    from app.modules.notifications.models import Notification, NotificationType
    from app.tests.integration.test_organization import _create_linked_employee

    headers = auth_header(client)
    dept = client.post(
        "/api/v1/departments",
        json={"name": "Training Notify Dept"},
        headers=headers,
    )
    assert dept.status_code in (201, 409), dept.text
    if dept.status_code == 201:
        department_id = dept.json()["id"]
    else:
        listing = client.get("/api/v1/departments?status=all", headers=headers)
        department_id = next(item["id"] for item in listing.json() if item["name"] == "Training Notify Dept")

    emp_user, _emp = _create_linked_employee(
        db_session,
        email="train.notify.emp@test.com",
        password="emppass123",
        department_id=department_id,
        first_name="Notify",
        last_name="Employee",
    )
    _create_linked_employee(
        db_session,
        email="train.notify.peer@test.com",
        password="emppass123",
        department_id=department_id,
        first_name="Peer",
        last_name="Employee",
    )

    created = client.post(
        "/api/v1/trainings",
        json={"title": "Company-wide Safety", "resource_url": "https://learn.example.com/safety"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    training_id = created.json()["id"]

    rows = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.TRAINING_RESOURCE_PUBLISHED,
            Notification.related_entity_type == "training",
            Notification.related_entity_id == training_id,
        )
        .all()
    )
    recipient_ids = {row.recipient_user_id for row in rows}
    assert emp_user.id in recipient_ids
    assert len(recipient_ids) >= 2
    assert all("Company-wide Safety" in row.message for row in rows)


def test_training_resource_url_create_update_and_assignment_exposure(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="train.resource@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    url = "https://learn.example.com/courses/safety"

    created = client.post(
        "/api/v1/trainings",
        json={
            "title": "Safety with resource",
            "description": "Read the portal",
            "resource_url": url,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["resource_url"] == url

    http_created = client.post(
        "/api/v1/trainings",
        json={"title": "HTTP resource", "resource_url": "http://intranet.local/t"},
        headers=headers,
    )
    assert http_created.status_code == 201, http_created.text
    assert http_created.json()["resource_url"] == "http://intranet.local/t"

    omitted = client.post(
        "/api/v1/trainings",
        json={"title": "No resource"},
        headers=headers,
    )
    assert omitted.status_code == 201, omitted.text
    assert omitted.json()["resource_url"] is None

    assert (
        client.post(
            "/api/v1/trainings",
            json={"title": "Bad", "resource_url": "javascript:alert(1)"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/trainings",
            json={"title": "Bad2", "resource_url": "not-a-url"},
            headers=headers,
        ).status_code
        == 422
    )

    training_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/trainings/{training_id}",
        json={"resource_url": "https://learn.example.com/courses/safety-v2"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["resource_url"] == "https://learn.example.com/courses/safety-v2"

    cleared = client.patch(
        f"/api/v1/trainings/{training_id}",
        json={"resource_url": None},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["resource_url"] is None

    assert (
        client.patch(
            f"/api/v1/trainings/{training_id}",
            json={"resource_url": "ftp://files.example.com/x"},
            headers=headers,
        ).status_code
        == 422
    )

    restore = client.patch(
        f"/api/v1/trainings/{training_id}",
        json={"resource_url": url},
        headers=headers,
    )
    assert restore.status_code == 200, restore.text

    catalog = client.get("/api/v1/trainings", headers=headers)
    assert catalog.status_code == 200
    match = next(item for item in catalog.json() if item["id"] == training_id)
    assert match["resource_url"] == url

    assigned = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training_id},
        headers=headers,
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["resource_url"] == url
    assert assigned.json()["title"] == "Safety with resource"

    me_list = client.get("/api/v1/me/onboarding/trainings", headers=candidate_headers)
    assert me_list.status_code == 200
    assert me_list.json()[0]["resource_url"] == url


def test_employee_sees_full_catalogue_and_completion_is_per_employee(client, db_session):
    from app.tests.integration.test_organization import _create_linked_employee

    headers = auth_header(client)
    dept = client.post(
        "/api/v1/departments",
        json={"name": "Catalogue Visibility Dept"},
        headers=headers,
    )
    assert dept.status_code in (201, 409), dept.text
    if dept.status_code == 201:
        department_id = dept.json()["id"]
    else:
        listing = client.get("/api/v1/departments?status=all", headers=headers)
        department_id = next(
            item["id"] for item in listing.json() if item["name"] == "Catalogue Visibility Dept"
        )

    _create_linked_employee(
        db_session,
        email="train.catalog.a@test.com",
        password="emppass123",
        department_id=department_id,
        first_name="Alpha",
        last_name="Learner",
    )
    _create_linked_employee(
        db_session,
        email="train.catalog.b@test.com",
        password="emppass123",
        department_id=department_id,
        first_name="Beta",
        last_name="Learner",
    )
    emp_a = auth_header(client, email="train.catalog.a@test.com", password="emppass123")
    emp_b = auth_header(client, email="train.catalog.b@test.com", password="emppass123")

    created_ids = []
    for title in ("Catalogue Course One", "Catalogue Course Two", "Catalogue Course Three"):
        created = client.post(
            "/api/v1/trainings",
            json={"title": title, "resource_url": f"https://learn.example.com/{title[-4:]}"},
            headers=headers,
        )
        assert created.status_code == 201, created.text
        created_ids.append(created.json()["id"])

    listed_a = client.get("/api/v1/me/trainings", headers=emp_a)
    assert listed_a.status_code == 200, listed_a.text
    titles_a = {item["title"] for item in listed_a.json()}
    assert {"Catalogue Course One", "Catalogue Course Two", "Catalogue Course Three"} <= titles_a
    assert all(item["status"] == "pending" for item in listed_a.json() if item["training_id"] in created_ids)

    target_id = created_ids[0]
    completed = client.patch(
        f"/api/v1/me/trainings/{target_id}/complete",
        headers=emp_a,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["training_id"] == target_id

    listed_a_after = client.get("/api/v1/me/trainings", headers=emp_a)
    assert listed_a_after.status_code == 200
    a_row = next(item for item in listed_a_after.json() if item["training_id"] == target_id)
    assert a_row["status"] == "completed"

    listed_b = client.get("/api/v1/me/trainings", headers=emp_b)
    assert listed_b.status_code == 200, listed_b.text
    b_row = next(item for item in listed_b.json() if item["training_id"] == target_id)
    assert b_row["status"] == "pending"

    again = client.patch(
        f"/api/v1/me/trainings/{target_id}/complete",
        headers=emp_a,
    )
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "completed"
