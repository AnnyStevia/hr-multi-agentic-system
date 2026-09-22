from unittest.mock import MagicMock

from app.modules.onboarding.models import Onboarding, OnboardingStatus
from app.shared.storage import get_storage_service
from app.shared.storage.base import StoredObject
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role
from app.tests.integration.test_onboarding import _hire

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def _onboarding_id(db_session, employee_id: int) -> int:
    return db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one().id


def _mock_storage(client) -> MagicMock:
    storage = MagicMock()
    storage.upload_file.return_value = StoredObject(
        key="k", bucket="b", content_type="application/pdf"
    )
    storage.generate_presigned_url.return_value = "https://s3.example/presigned"
    client.app.dependency_overrides[get_storage_service] = lambda: storage
    return storage


def test_progress_tasks_only(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="progress.tasks@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    t1 = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Task A", "task_type": "acknowledgement"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Task B", "task_type": "acknowledgement"},
        headers=headers,
    )
    client.patch(
        f"/api/v1/me/onboarding/tasks/{t1['id']}/complete",
        headers=candidate_headers,
    )

    progress = client.get("/api/v1/me/onboarding/progress", headers=candidate_headers)
    assert progress.status_code == 200, progress.text
    body = progress.json()
    assert body["tasks"] == {"total": 2, "completed": 1, "pending": 1}
    assert body["trainings"] == {"total": 0, "completed": 0, "pending": 0}
    assert body["documents"]["total"] == 0
    assert body["overall_percentage"] == 50
    assert body["status"] == "in_progress"


def test_progress_trainings_only(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="progress.train@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Course A"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={
            "training_id": client.post(
                "/api/v1/trainings",
                json={"title": "Course B"},
                headers=headers,
            ).json()["id"]
        },
        headers=headers,
    )
    client.patch(
        f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
        headers=candidate_headers,
    )

    progress = client.get(
        f"/api/v1/onboarding/{onboarding_id}/progress",
        headers=headers,
    ).json()
    assert progress["tasks"]["total"] == 0
    assert progress["trainings"] == {"total": 2, "completed": 1, "pending": 1}
    assert progress["overall_percentage"] == 50


def test_progress_combined_and_documents_ignored(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="progress.combo@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    _mock_storage(client)

    t1 = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Task 1", "task_type": "acknowledgement"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Task 2", "task_type": "acknowledgement"},
        headers=headers,
    )
    client.patch(
        f"/api/v1/me/onboarding/tasks/{t1['id']}/complete",
        headers=candidate_headers,
    )

    training = client.post(
        "/api/v1/trainings",
        json={"title": "Safety"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    ).json()
    client.patch(
        f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
        headers=candidate_headers,
    )

    uploaded = client.post(
        "/api/v1/me/documents",
        headers=candidate_headers,
        data={"document_type": "id_document"},
        files={"file": ("id.pdf", PDF, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text

    progress = client.get("/api/v1/me/onboarding/progress", headers=candidate_headers).json()
    # 2 tasks (1 done) + 1 training (1 done) => (1+1)/(2+1) = 67%
    assert progress["overall_percentage"] == 67
    assert progress["documents"]["total"] == 1
    assert progress["status"] == "in_progress"


def test_progress_zero_when_no_trackables(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="progress.zero@test.com"
    )
    progress = client.get("/api/v1/me/onboarding/progress", headers=candidate_headers).json()
    assert progress["overall_percentage"] == 0
    assert progress["tasks"]["total"] == 0
    assert progress["trainings"]["total"] == 0
    assert headers is not None
    assert body["hired_employee_id"] is not None


def test_employee_cannot_access_other_progress(client, db_session):
    _a, _j, owner_headers, headers, body = _hire(
        client, db_session, email="progress.owner@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    other = create_candidate_user(
        db_session, email="progress.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")
    assert client.get("/api/v1/me/onboarding/progress", headers=other_headers).status_code == 404
    assert (
        client.get(
            f"/api/v1/onboarding/{onboarding_id}/progress",
            headers=other_headers,
        ).status_code
        == 403
    )
    assert owner_headers is not None
    assert client.get(f"/api/v1/onboarding/{onboarding_id}/progress", headers=headers).status_code == 200


def test_final_task_completes_onboarding_non_final_does_not(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="progress.final@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    first = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "First", "task_type": "acknowledgement"},
        headers=headers,
    ).json()
    second = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Last", "task_type": "acknowledgement"},
        headers=headers,
    ).json()

    client.patch(
        f"/api/v1/me/onboarding/tasks/{first['id']}/complete",
        headers=candidate_headers,
    )
    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.IN_PROGRESS
    assert onboarding.completed_at is None
    assert client.get("/api/v1/careers/jobs", headers=candidate_headers).status_code == 403
    assert client.get("/api/v1/me/employee-home", headers=candidate_headers).status_code == 403

    client.patch(
        f"/api/v1/me/onboarding/tasks/{second['id']}/complete",
        headers=candidate_headers,
    )
    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.COMPLETED
    assert onboarding.completed_at is not None

    progress = client.get("/api/v1/me/onboarding/progress", headers=candidate_headers).json()
    assert progress["status"] == "completed"
    assert progress["completed_at"] is not None
    assert progress["overall_percentage"] == 100
    assert client.get("/api/v1/careers/jobs", headers=candidate_headers).status_code == 200
    assert client.get("/api/v1/me/employee-home", headers=candidate_headers).status_code == 200


def test_trainings_and_documents_do_not_complete_onboarding(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="progress.nocomplete@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    _mock_storage(client)

    client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Still pending"},
        headers=headers,
    )
    training = client.post(
        "/api/v1/trainings",
        json={"title": "All done course"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    ).json()
    assert (
        client.patch(
            f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
            headers=candidate_headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/me/documents",
            headers=candidate_headers,
            data={"document_type": "contract"},
            files={"file": ("c.pdf", PDF, "application/pdf")},
        ).status_code
        == 201
    )

    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.IN_PROGRESS
    assert onboarding.completed_at is None


def test_unauthorized_progress_rejected(client, db_session):
    _a, _j, _cand, headers, body = _hire(client, db_session, email="progress.unauth@test.com")
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    assert client.get("/api/v1/me/onboarding/progress").status_code == 401
    assert client.get(f"/api/v1/onboarding/{onboarding_id}/progress").status_code == 401

    create_user_with_role(
        db_session,
        email="progress.plain.emp@test.com",
        password="emppass123",
        role_name="employee",
    )
    plain = auth_header(client, email="progress.plain.emp@test.com", password="emppass123")
    assert (
        client.get(f"/api/v1/onboarding/{onboarding_id}/progress", headers=plain).status_code
        == 403
    )
    assert headers is not None
