import pytest

from app.tests.integration.test_application_review import _hr_headers, _submit_application


def _move_to(client, application_id: int, headers: dict, statuses: list[str]) -> None:
    for status in statuses:
        moved = client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": status},
            headers=headers,
        )
        assert moved.status_code == 200, moved.text


@pytest.mark.parametrize(
    "setup_path,target",
    [
        ([], "screening"),
        ([], "rejected"),
        (["screening"], "shortlisted"),
        (["screening"], "rejected"),
        (["screening", "shortlisted"], "rejected"),
    ],
)
def test_api_allows_valid_status_transitions(client, db_session, setup_path, target):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _hr_headers(client, db_session)
    _move_to(client, application["id"], headers, setup_path)

    response = client.patch(
        f"/api/v1/applications/{application['id']}/status",
        json={"status": target},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == target


def test_api_rejects_direct_hire_status_update(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _hr_headers(client, db_session)
    _move_to(client, application["id"], headers, ["screening", "shortlisted"])
    response = client.patch(
        f"/api/v1/applications/{application['id']}/status",
        json={"status": "hired"},
        headers=headers,
    )
    assert response.status_code == 400
    assert "interview outcome" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "setup,target",
    [
        ("submitted", "shortlisted"),
        ("screening", "submitted"),
        ("shortlisted", "submitted"),
        ("shortlisted", "screening"),
        ("rejected", "screening"),
        ("rejected", "shortlisted"),
        ("rejected", "submitted"),
    ],
)
def test_api_rejects_invalid_status_transitions(client, db_session, setup, target):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _hr_headers(client, db_session)
    application_id = application["id"]

    if setup == "screening":
        _move_to(client, application_id, headers, ["screening"])
    elif setup == "shortlisted":
        _move_to(client, application_id, headers, ["screening", "shortlisted"])
    elif setup == "rejected":
        _move_to(client, application_id, headers, ["rejected"])

    response = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": target},
        headers=headers,
    )
    assert response.status_code == 400
    detail = client.get(f"/api/v1/applications/{application_id}", headers=headers)
    assert detail.json()["status"] == setup
