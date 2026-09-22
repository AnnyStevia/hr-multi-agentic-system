from app.modules.onboarding.models import Onboarding, OnboardingTask, OnboardingTaskType
from app.modules.onboarding.service import OnboardingService
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.employees.repository import EmployeeRepository
from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_onboarding import _hire


def _onboarding_id(db_session, employee_id: int) -> int:
    return db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one().id


def test_hr_can_create_update_deactivate_template(client, db_session):
    create_user_with_role(db_session, email="hr.tpl@test.com", password="hrpass123", role_name="hr")
    headers = auth_header(client, "hr.tpl@test.com", "hrpass123")

    created = client.post(
        "/api/v1/onboarding/task-templates",
        json={
            "title": "Upload ID card",
            "description": "Government ID",
            "task_type": "document",
            "document_type": "id_document",
            "is_required": True,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["task_type"] == "document"
    assert body["is_required"] is True
    assert body["is_active"] is True

    updated = client.patch(
        f"/api/v1/onboarding/task-templates/{body['id']}",
        json={"title": "Upload identification", "is_required": False},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Upload identification"
    assert updated.json()["is_required"] is False

    deactivated = client.patch(
        f"/api/v1/onboarding/task-templates/{body['id']}",
        json={"is_active": False},
        headers=headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False


def test_employee_cannot_manage_templates(client, db_session):
    create_user_with_role(
        db_session, email="emp.tpl@test.com", password="emppass123", role_name="employee"
    )
    headers = auth_header(client, "emp.tpl@test.com", "emppass123")
    assert (
        client.post(
            "/api/v1/onboarding/task-templates",
            json={"title": "Nope", "task_type": "manual"},
            headers=headers,
        ).status_code
        == 403
    )


def test_invalid_task_type_rejected(client):
    headers = auth_header(client)
    response = client.post(
        "/api/v1/onboarding/task-templates",
        json={"title": "Bad type", "task_type": "payroll"},
        headers=headers,
    )
    assert response.status_code == 422


def test_active_templates_assigned_on_hire(client, db_session):
    headers = auth_header(client)
    active = client.post(
        "/api/v1/onboarding/task-templates",
        json={
            "title": "Complete personal information seed",
            "task_type": "profile_personal_info",
            "is_required": True,
        },
        headers=headers,
    ).json()
    inactive = client.post(
        "/api/v1/onboarding/task-templates",
        json={
            "title": "Inactive meet CEO",
            "task_type": "manual",
            "is_required": False,
            "is_active": False,
        },
        headers=headers,
    ).json()
    client.patch(
        f"/api/v1/onboarding/task-templates/{inactive['id']}",
        json={"is_active": False},
        headers=headers,
    )

    _a, _j, _c, _h, body = _hire(client, db_session, email="tpl.assign@test.com")
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    tasks = (
        db_session.query(OnboardingTask)
        .filter(OnboardingTask.onboarding_id == onboarding_id)
        .all()
    )
    titles = {task.title for task in tasks}
    assert "Complete personal information seed" in titles
    assert "Inactive meet CEO" not in titles
    assigned = next(task for task in tasks if task.template_id == active["id"])
    assert assigned.task_type == OnboardingTaskType.PROFILE_PERSONAL_INFO
    assert assigned.is_required is True
    assert assigned.title == "Complete personal information seed"


def test_template_snapshot_preserved_after_edit(client, db_session):
    headers = auth_header(client)
    template = client.post(
        "/api/v1/onboarding/task-templates",
        json={"title": "Snapshot title", "task_type": "education", "is_required": True},
        headers=headers,
    ).json()
    _a, _j, _c, _h, body = _hire(client, db_session, email="tpl.snap@test.com")
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    task = (
        db_session.query(OnboardingTask)
        .filter(
            OnboardingTask.onboarding_id == onboarding_id,
            OnboardingTask.template_id == template["id"],
        )
        .one()
    )
    client.patch(
        f"/api/v1/onboarding/task-templates/{template['id']}",
        json={"title": "Changed later", "is_required": False},
        headers=headers,
    )
    db_session.refresh(task)
    assert task.title == "Snapshot title"
    assert task.is_required is True


def test_assign_templates_idempotent(client, db_session):
    headers = auth_header(client)
    client.post(
        "/api/v1/onboarding/task-templates",
        json={"title": "Idempotent task", "task_type": "manual"},
        headers=headers,
    )
    _a, _j, _c, _h, body = _hire(client, db_session, email="tpl.idem@test.com")
    onboarding = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == body["hired_employee_id"])
        .one()
    )
    before = (
        db_session.query(OnboardingTask)
        .filter(OnboardingTask.onboarding_id == onboarding.id)
        .count()
    )
    service = OnboardingService(OnboardingRepository(db_session), EmployeeRepository(db_session))
    service._assign_active_templates(onboarding, commit=True)
    after = (
        db_session.query(OnboardingTask)
        .filter(OnboardingTask.onboarding_id == onboarding.id)
        .count()
    )
    assert before == after


def test_required_tasks_determine_completion_optional_do_not_block(client, db_session):
    headers = auth_header(client)
    _a, _j, candidate_headers, _h, body = _hire(
        client, db_session, email="tpl.complete@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    required = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Required only", "is_required": True, "task_type": "manual"},
        headers=headers,
    ).json()
    optional = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Optional later", "is_required": False, "task_type": "manual"},
        headers=headers,
    ).json()

    client.patch(
        f"/api/v1/onboarding/tasks/{required['id']}/complete",
        headers=headers,
    )
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    db_session.refresh(onboarding)
    assert onboarding.status.value == "completed"

    optional_task = db_session.query(OnboardingTask).filter(OnboardingTask.id == optional["id"]).one()
    assert optional_task.status.value == "pending"


def test_delete_used_template_soft_deactivates(client, db_session):
    headers = auth_header(client)
    template = client.post(
        "/api/v1/onboarding/task-templates",
        json={"title": "Used template", "task_type": "document", "document_type": "id_document"},
        headers=headers,
    ).json()
    _hire(client, db_session, email="tpl.used@test.com")
    deleted = client.delete(
        f"/api/v1/onboarding/task-templates/{template['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["is_active"] is False
    assert (
        db_session.query(OnboardingTask)
        .filter(OnboardingTask.template_id == template["id"])
        .count()
        > 0
    )


def test_manual_task_still_works(client, db_session):
    headers = auth_header(client)
    _a, _j, candidate_headers, _h, body = _hire(
        client, db_session, email="tpl.manual@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Classic checklist item"},
        headers=headers,
    )
    assert task.status_code == 201, task.text
    assert task.json()["task_type"] == "manual"
    assert task.json()["is_required"] is True
    completed = client.patch(
        f"/api/v1/onboarding/tasks/{task.json()['id']}/complete",
        headers=headers,
    )
    assert completed.status_code == 200
