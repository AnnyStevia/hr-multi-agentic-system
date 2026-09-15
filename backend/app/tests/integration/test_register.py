from app.core.security import verify_password
from app.modules.identity.models import Candidate, User
from app.tests.helpers import auth_header

REGISTER_PAYLOAD = {
    "first_name": "Lina",
    "last_name": "Trabelsi",
    "email": "lina.candidate@test.com",
    "password": "candidate123",
}


def test_register_creates_candidate_and_returns_token(client, db_session):
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "hashed_password" not in data
    assert "password" not in data
    assert REGISTER_PAYLOAD["password"] not in str(data)

    user = db_session.query(User).filter(User.email == REGISTER_PAYLOAD["email"]).one()
    assert user.hashed_password != REGISTER_PAYLOAD["password"]
    assert verify_password(REGISTER_PAYLOAD["password"], user.hashed_password)
    assert [ur.role.name for ur in user.user_roles] == ["candidate"]
    assert db_session.query(Candidate).filter(Candidate.user_id == user.id).one() is not None

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["full_name"] == "Lina Trabelsi"
    assert [role["name"] for role in body["roles"]] == ["candidate"]
    assert "hashed_password" not in body
    assert "password" not in body


def test_registered_candidate_can_login(client):
    created = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert created.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert any(role["name"] == "candidate" for role in me.json()["roles"])


def test_admin_and_hr_login_still_work(client, db_session):
    from app.tests.helpers import create_user_with_role

    admin = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "testpass123"},
    )
    assert admin.status_code == 200

    create_user_with_role(
        db_session,
        email="hr.login@test.com",
        password="hrpass123",
        role_name="hr",
    )
    hr = client.post(
        "/api/v1/auth/login",
        json={"email": "hr.login@test.com", "password": "hrpass123"},
    )
    assert hr.status_code == 200


def test_register_rejects_duplicate_email(client):
    first = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert second.status_code == 409
    assert "email" in second.json()["detail"].lower()


def test_register_rejects_invalid_email(client):
    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "email": "not-an-email"},
    )
    assert response.status_code == 422


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "password": "short"},
    )
    assert response.status_code == 422


def test_register_rejects_missing_fields(client):
    response = client.post("/api/v1/auth/register", json={"email": "incomplete@test.com"})
    assert response.status_code == 422


def test_register_rejects_role_in_body(client):
    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "role": "admin"},
    )
    assert response.status_code == 422


def test_register_does_not_require_auth(client):
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    assert auth_header(client)["Authorization"].startswith("Bearer ")
