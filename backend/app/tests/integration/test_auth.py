def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_get_me_authenticated(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "testpass123"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@test.com"
    assert data["full_name"] == "System Admin"
    assert any(role["name"] == "admin" for role in data["roles"])
    assert "users:read" in data["permissions"]


def test_get_me_unauthenticated(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_login_accepts_local_domain_email(db_session, client):
    from app.core.security import get_password_hash
    from app.modules.identity.models import User

    db_session.add(
        User(
            email="admin@hr-platform.local",
            hashed_password=get_password_hash("admin123"),
            first_name="System",
            last_name="Admin",
            is_active=True,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@hr-platform.local", "password": "admin123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
