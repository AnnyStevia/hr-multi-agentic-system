from app.tests.helpers import auth_header, create_department, create_user_with_role, job_payload


def _payload(client, **overrides) -> dict:
    department = create_department(client)
    return job_payload(department["id"], **overrides)


def test_admin_can_create_job(client):
    response = client.post("/api/v1/jobs", json=_payload(client), headers=auth_header(client))
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Backend Engineer"
    assert data["status"] == "draft"
    assert data["department"] == "Engineering"
    assert data["department_id"] is not None
    assert data["published_at"] is None
    assert "hashed_password" not in data
    assert "password" not in data


def test_hr_can_create_job(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.jobs@test.com",
        password="hrpass123",
        role_name="hr",
    )
    response = client.post(
        "/api/v1/jobs",
        json=_payload(client),
        headers=auth_header(client, "hr.jobs@test.com", "hrpass123"),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_employee_cannot_create_job(client, db_session):
    create_user_with_role(
        db_session,
        email="employee@test.com",
        password="emppass123",
        role_name="employee",
    )
    response = client.post(
        "/api/v1/jobs",
        json=_payload(client),
        headers=auth_header(client, "employee@test.com", "emppass123"),
    )
    assert response.status_code == 403


def test_unauthorized_cannot_create_job(client):
    response = client.post("/api/v1/jobs", json=_payload(client))
    assert response.status_code == 401


def test_invalid_job_data_is_rejected(client):
    response = client.post(
        "/api/v1/jobs",
        json={"title": "", "description": ""},
        headers=auth_header(client),
    )
    assert response.status_code == 422


def test_inactive_department_is_rejected_for_jobs(client):
    department = create_department(client, name="Legacy")
    client.patch(f"/api/v1/departments/{department['id']}/deactivate", headers=auth_header(client))
    response = client.post(
        "/api/v1/jobs",
        json=job_payload(department["id"]),
        headers=auth_header(client),
    )
    assert response.status_code == 400


def test_hr_can_publish_and_close_job(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.jobs@test.com",
        password="hrpass123",
        role_name="hr",
    )
    headers = auth_header(client, "hr.jobs@test.com", "hrpass123")
    created = client.post("/api/v1/jobs", json=_payload(client), headers=headers)
    job_id = created.json()["id"]

    published = client.post(f"/api/v1/jobs/{job_id}/publish", headers=headers)
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None

    closed = client.post(f"/api/v1/jobs/{job_id}/close", headers=headers)
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_at"] is not None


def test_cannot_close_draft_job(client):
    headers = auth_header(client)
    created = client.post("/api/v1/jobs", json=_payload(client), headers=headers)
    job_id = created.json()["id"]
    response = client.post(f"/api/v1/jobs/{job_id}/close", headers=headers)
    assert response.status_code == 409


def test_cannot_publish_closed_job(client):
    headers = auth_header(client)
    created = client.post("/api/v1/jobs", json=_payload(client), headers=headers)
    job_id = created.json()["id"]
    client.post(f"/api/v1/jobs/{job_id}/publish", headers=headers)
    client.post(f"/api/v1/jobs/{job_id}/close", headers=headers)
    response = client.post(f"/api/v1/jobs/{job_id}/publish", headers=headers)
    assert response.status_code == 409


def _candidate_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Lina",
            "last_name": "Trabelsi",
            "email": "lina.jobs@test.com",
            "password": "candidate123",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _published_and_hidden_jobs(client):
    headers = auth_header(client)
    payload = _payload(client)
    draft = client.post("/api/v1/jobs", json=payload, headers=headers).json()
    published = client.post(
        "/api/v1/jobs",
        json={**payload, "title": "Published Role"},
        headers=headers,
    ).json()
    closed = client.post(
        "/api/v1/jobs",
        json={**payload, "title": "Closed Role"},
        headers=headers,
    ).json()

    client.post(f"/api/v1/jobs/{published['id']}/publish", headers=headers)
    client.post(f"/api/v1/jobs/{closed['id']}/publish", headers=headers)
    client.post(f"/api/v1/jobs/{closed['id']}/close", headers=headers)
    return draft, published, closed


def test_candidate_sees_only_published_jobs(client):
    draft, published, closed = _published_and_hidden_jobs(client)
    candidate = _candidate_headers(client)

    career_list = client.get("/api/v1/careers/jobs", headers=candidate)
    assert career_list.status_code == 200
    titles = [job["title"] for job in career_list.json()]
    assert "Published Role" in titles
    assert "Backend Engineer" not in titles
    assert "Closed Role" not in titles

    detail = client.get(f"/api/v1/careers/jobs/{published['id']}", headers=candidate)
    assert detail.status_code == 200
    assert detail.json()["title"] == "Published Role"
    assert client.get(f"/api/v1/careers/jobs/{draft['id']}", headers=candidate).status_code == 404
    assert client.get(f"/api/v1/careers/jobs/{closed['id']}", headers=candidate).status_code == 404


def test_anonymous_cannot_list_career_jobs(client):
    response = client.get("/api/v1/careers/jobs")
    assert response.status_code == 401


def test_hr_and_employee_cannot_access_career_jobs(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.careers@test.com",
        password="hrpass123",
        role_name="hr",
    )
    create_user_with_role(
        db_session,
        email="employee.careers@test.com",
        password="emppass123",
        role_name="employee",
    )
    assert (
        client.get(
            "/api/v1/careers/jobs",
            headers=auth_header(client, "hr.careers@test.com", "hrpass123"),
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/careers/jobs",
            headers=auth_header(client, "employee.careers@test.com", "emppass123"),
        ).status_code
        == 403
    )


def test_anonymous_public_jobs_endpoint_is_removed(client):
    assert client.get("/api/v1/public/jobs").status_code == 404
