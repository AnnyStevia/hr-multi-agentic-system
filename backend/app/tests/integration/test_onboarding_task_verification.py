from unittest.mock import MagicMock

from app.modules.onboarding.models import Onboarding, OnboardingStatus, OnboardingTask
from app.shared.storage import get_storage_service
from app.shared.storage.base import StoredObject
from app.tests.helpers import auth_header
from app.tests.integration.test_onboarding import _hire

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def _onboarding_id(db_session, employee_id: int) -> int:
    return db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one().id


def _mock_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file.return_value = StoredObject(
        key="k", bucket="b", content_type="application/pdf"
    )
    storage.generate_presigned_url.return_value = "https://s3.example/presigned"
    return storage


def _use_storage(client, storage: MagicMock) -> None:
    client.app.dependency_overrides[get_storage_service] = lambda: storage


def _task_status(db_session, task_id: int) -> str:
    db_session.expire_all()
    return db_session.query(OnboardingTask).filter(OnboardingTask.id == task_id).one().status.value


def test_profile_personal_info_auto_verifies_and_reopens(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.pii@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Fill PII", "task_type": "profile_personal_info"},
        headers=headers,
    ).json()
    # Keep onboarding in progress so sync can reopen auto tasks.
    client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Blocker ack", "task_type": "acknowledgement", "is_required": True},
        headers=headers,
    )

    assert _task_status(db_session, task["id"]) == "pending"

    updated = client.patch(
        "/api/v1/me/profile",
        headers=candidate_headers,
        json={
            "phone": "+216 20 111 222",
            "date_of_birth": "1994-01-15",
            "address": "1 Test St",
            "city": "Tunis",
            "country": "Tunisia",
        },
    )
    assert updated.status_code == 200, updated.text
    assert _task_status(db_session, task["id"]) == "completed"

    cleared = client.patch(
        "/api/v1/me/profile",
        headers=candidate_headers,
        json={"city": ""},
    )
    assert cleared.status_code == 200, cleared.text
    assert _task_status(db_session, task["id"]) == "pending"


def test_profile_picture_auto_verifies_and_reopens(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.pic@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    storage = _mock_storage()
    storage.upload_file.return_value = StoredObject(
        key="pic", bucket="b", content_type="image/png"
    )
    _use_storage(client, storage)

    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Add photo", "task_type": "profile_picture"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Blocker ack", "task_type": "acknowledgement", "is_required": True},
        headers=headers,
    )

    uploaded = client.post(
        "/api/v1/me/profile/picture",
        headers=candidate_headers,
        files={"file": ("avatar.png", PNG, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert _task_status(db_session, task["id"]) == "completed"

    deleted = client.delete("/api/v1/me/profile/picture", headers=candidate_headers)
    assert deleted.status_code == 204
    assert _task_status(db_session, task["id"]) == "pending"


def test_education_and_experience_auto_verify(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.edu@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    edu_task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Add education", "task_type": "education"},
        headers=headers,
    ).json()
    exp_task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Add experience", "task_type": "experience"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Blocker ack", "task_type": "acknowledgement", "is_required": True},
        headers=headers,
    )

    edu = client.post(
        "/api/v1/me/profile/education",
        headers=candidate_headers,
        json={
            "institution": "ENIT",
            "degree": "Engineering",
            "field_of_study": "CS",
            "start_date": "2018-09-01",
            "end_date": "2022-06-30",
        },
    )
    assert edu.status_code == 201, edu.text
    assert _task_status(db_session, edu_task["id"]) == "completed"

    exp = client.post(
        "/api/v1/me/profile/experience",
        headers=candidate_headers,
        json={
            "company": "Acme",
            "position": "Dev",
            "start_date": "2023-01-01",
            "end_date": None,
        },
    )
    assert exp.status_code == 201, exp.text
    assert _task_status(db_session, exp_task["id"]) == "completed"

    assert (
        client.delete(
            f"/api/v1/me/profile/education/{edu.json()['id']}",
            headers=candidate_headers,
        ).status_code
        == 204
    )
    assert _task_status(db_session, edu_task["id"]) == "pending"

    assert (
        client.delete(
            f"/api/v1/me/profile/experience/{exp.json()['id']}",
            headers=candidate_headers,
        ).status_code
        == 204
    )
    assert _task_status(db_session, exp_task["id"]) == "pending"


def test_document_task_requires_matching_type(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.doc@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    storage = _mock_storage()
    _use_storage(client, storage)

    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={
            "title": "Upload ID",
            "task_type": "document",
            "document_type": "id_document",
        },
        headers=headers,
    ).json()
    assert task["document_type"] == "id_document"
    client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Blocker ack", "task_type": "acknowledgement", "is_required": True},
        headers=headers,
    )

    wrong = client.post(
        "/api/v1/me/documents",
        headers=candidate_headers,
        data={"document_type": "contract"},
        files={"file": ("c.pdf", PDF, "application/pdf")},
    )
    assert wrong.status_code == 201, wrong.text
    assert _task_status(db_session, task["id"]) == "pending"

    right = client.post(
        "/api/v1/me/documents",
        headers=candidate_headers,
        data={"document_type": "id_document"},
        files={"file": ("id.pdf", PDF, "application/pdf")},
    )
    assert right.status_code == 201, right.text
    assert _task_status(db_session, task["id"]) == "completed"

    deleted = client.delete(
        f"/api/v1/employees/{body['hired_employee_id']}/documents/{right.json()['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert _task_status(db_session, task["id"]) == "pending"


def test_training_task_auto_verifies_when_assignment_completed(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.train@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Safety 101", "description": "Basics"},
        headers=headers,
    ).json()

    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={
            "title": "Do safety training",
            "task_type": "training",
            "training_id": training["id"],
        },
        headers=headers,
    ).json()
    assert task["training_id"] == training["id"]
    assert _task_status(db_session, task["id"]) == "pending"

    assignments = client.get("/api/v1/me/onboarding/trainings", headers=candidate_headers)
    assert assignments.status_code == 200, assignments.text
    assert len(assignments.json()) == 1
    assignment_id = assignments.json()[0]["id"]

    completed = client.patch(
        f"/api/v1/me/onboarding/trainings/{assignment_id}/complete",
        headers=candidate_headers,
    )
    assert completed.status_code == 200, completed.text
    assert _task_status(db_session, task["id"]) == "completed"


def test_acknowledgement_and_manual_never_auto_verify(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.ack@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    ack = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Ack handbook", "task_type": "acknowledgement"},
        headers=headers,
    ).json()
    manual = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Desk setup", "task_type": "manual"},
        headers=headers,
    ).json()

    client.patch(
        "/api/v1/me/profile",
        headers=candidate_headers,
        json={
            "phone": "+216 20 000 000",
            "date_of_birth": "1990-01-01",
            "address": "X",
            "city": "Y",
            "country": "Z",
        },
    )
    assert _task_status(db_session, ack["id"]) == "pending"
    assert _task_status(db_session, manual["id"]) == "pending"

    acknowledged = client.patch(
        f"/api/v1/me/onboarding/tasks/{ack['id']}/acknowledge",
        headers=candidate_headers,
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["status"] == "completed"

    hr_done = client.patch(
        f"/api/v1/onboarding/tasks/{manual['id']}/complete",
        headers=headers,
    )
    assert hr_done.status_code == 200, hr_done.text
    assert hr_done.json()["status"] == "completed"


def test_employee_cannot_bypass_automatic_or_manual_tasks(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.security.emp@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    auto = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "PII", "task_type": "profile_personal_info"},
        headers=headers,
    ).json()
    manual = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Manual", "task_type": "manual"},
        headers=headers,
    ).json()

    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{auto['id']}/complete",
            headers=candidate_headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{auto['id']}/acknowledge",
            headers=candidate_headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{manual['id']}/acknowledge",
            headers=candidate_headers,
        ).status_code
        == 400
    )


def test_hr_cannot_complete_non_manual_tasks(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.security.hr@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    auto = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "PII", "task_type": "profile_personal_info"},
        headers=headers,
    ).json()
    ack = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Ack", "task_type": "acknowledgement"},
        headers=headers,
    ).json()

    assert (
        client.patch(
            f"/api/v1/onboarding/tasks/{auto['id']}/complete",
            headers=headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/onboarding/tasks/{ack['id']}/complete",
            headers=headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/onboarding/tasks/{auto['id']}",
            json={"status": "completed"},
            headers=headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/onboarding/tasks/{ack['id']}",
            json={"status": "completed"},
            headers=headers,
        ).status_code
        == 400
    )
    assert candidate_headers is not None


def test_required_auto_tasks_complete_onboarding_optional_do_not_block(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.complete@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    required = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={
            "title": "Required PII",
            "task_type": "profile_personal_info",
            "is_required": True,
        },
        headers=headers,
    ).json()
    optional = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={
            "title": "Optional ack",
            "task_type": "acknowledgement",
            "is_required": False,
        },
        headers=headers,
    ).json()

    client.patch(
        "/api/v1/me/profile",
        headers=candidate_headers,
        json={
            "phone": "+216 20 333 444",
            "date_of_birth": "1992-03-03",
            "address": "Addr",
            "city": "City",
            "country": "Country",
        },
    )
    assert _task_status(db_session, required["id"]) == "completed"
    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.COMPLETED
    assert _task_status(db_session, optional["id"]) == "pending"


def test_sync_is_idempotent_and_does_not_reopen_completed_onboarding(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="verify.idempotent@test.com"
    )
    employee_id = body["hired_employee_id"]
    onboarding_id = _onboarding_id(db_session, employee_id)
    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Required PII", "task_type": "profile_personal_info"},
        headers=headers,
    ).json()

    payload = {
        "phone": "+216 20 555 666",
        "date_of_birth": "1991-04-04",
        "address": "A",
        "city": "B",
        "country": "C",
    }
    assert client.patch("/api/v1/me/profile", headers=candidate_headers, json=payload).status_code == 200
    assert _task_status(db_session, task["id"]) == "completed"
    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.COMPLETED
    completed_at = onboarding.completed_at

    assert client.patch("/api/v1/me/profile", headers=candidate_headers, json=payload).status_code == 200
    assert client.patch(
        "/api/v1/me/profile",
        headers=candidate_headers,
        json={"city": ""},
    ).status_code == 200

    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.COMPLETED
    assert onboarding.completed_at == completed_at
    assert _task_status(db_session, task["id"]) == "completed"


def test_training_template_assign_creates_assignment(client, db_session):
    headers = auth_header(client)
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Company orientation clone", "description": "Orient"},
        headers=headers,
    ).json()
    template = client.post(
        "/api/v1/onboarding/task-templates",
        json={
            "title": "Complete orientation clone",
            "task_type": "training",
            "training_id": training["id"],
            "is_required": True,
        },
        headers=headers,
    ).json()
    assert template["training_id"] == training["id"]

    _a, _j, candidate_headers, _h, body = _hire(
        client, db_session, email="verify.assign.train@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    tasks = client.get(f"/api/v1/onboarding/{onboarding_id}/tasks", headers=headers).json()
    training_tasks = [t for t in tasks if t["task_type"] == "training"]
    assert any(t["training_id"] == training["id"] for t in training_tasks)

    assignments = client.get("/api/v1/me/onboarding/trainings", headers=candidate_headers)
    assert assignments.status_code == 200
    assert any(a["training_id"] == training["id"] for a in assignments.json())
