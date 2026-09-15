from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.modules.identity.models import Candidate, Role, User, UserRole


def login(client: TestClient, email: str = "admin@test.com", password: str = "testpass123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(client: TestClient, email: str = "admin@test.com", password: str = "testpass123") -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, email, password)}"}


def create_user_with_role(
    db: Session,
    *,
    email: str,
    password: str,
    role_name: str,
    first_name: str = "Test",
    last_name: str = "User",
    is_active: bool = True,
) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role is not None, f"Role {role_name} was not seeded"
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    return user


def create_department(client: TestClient, name: str = "Engineering", headers: dict[str, str] | None = None) -> dict:
    auth = headers or auth_header(client)
    response = client.post("/api/v1/departments", json={"name": name}, headers=auth)
    if response.status_code == 409:
        listing = client.get("/api/v1/departments?status=all", headers=auth)
        assert listing.status_code == 200, listing.text
        match = next((item for item in listing.json() if item["name"] == name), None)
        assert match is not None, listing.text
        return match
    assert response.status_code == 201, response.text
    return response.json()


def job_payload(department_id: int | None = None, **overrides) -> dict:
    payload = {
        "title": "Backend Engineer",
        "description": "Build the HR platform APIs.",
        "position": "Software Engineer",
        "location": "Tunis",
        "employment_type": "full_time",
        "requirements": "Python, FastAPI",
    }
    if department_id is not None:
        payload["department_id"] = department_id
    payload.update(overrides)
    return payload


def hr_payload(department_id: int, **overrides) -> dict:
    payload = {
        "first_name": "Amina",
        "last_name": "Benali",
        "email": "amina.hr@hr-platform.local",
        "password": "hrpass123",
        "phone": "+216 20 111 222",
        "department_id": department_id,
        "position": "HR Officer",
        "hire_date": "2024-01-15",
    }
    payload.update(overrides)
    return payload


def create_candidate_user(
    db: Session,
    *,
    email: str,
    password: str,
    first_name: str = "Lina",
    last_name: str = "Trabelsi",
) -> User:
    user = create_user_with_role(
        db,
        email=email,
        password=password,
        role_name="candidate",
        first_name=first_name,
        last_name=last_name,
    )
    db.add(Candidate(user_id=user.id))
    db.commit()
    return user
