from datetime import date

from app.core.security import get_password_hash
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.identity.models import Role, User, UserRole
from app.tests.helpers import auth_header, create_department, create_user_with_role


def _create_linked_employee(
    db_session,
    *,
    email: str,
    password: str,
    department_id: int,
    first_name: str = "Sam",
    last_name: str = "Staff",
    position: str = "Engineer",
    position_id: int | None = None,
    manager_id: int | None = None,
) -> tuple[User, Employee]:
    role = db_session.query(Role).filter(Role.name == "employee").one()
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    employee = Employee(
        employee_number="PENDING",
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone="+21620111222",
        department_id=department_id,
        position=position,
        position_id=position_id,
        manager_id=manager_id,
        hire_date=date(2024, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=user.id,
    )
    db_session.add(employee)
    db_session.flush()
    employee.employee_number = f"EMP-{employee.id:06d}"
    db_session.commit()
    db_session.refresh(employee)
    return user, employee


def test_hr_assigns_position_and_employee_can_view(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="EngOrg")
    position = client.post(
        "/api/v1/positions",
        json={"title": "Software Engineer", "department_id": department["id"]},
        headers=headers,
    ).json()

    created = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Lina",
            "last_name": "Dev",
            "email": "lina.dev@test.com",
            "phone": "+216 20 555 666",
            "department_id": department["id"],
            "position": "Temp Title",
            "hire_date": "2024-03-01",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    employee_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/employees/{employee_id}",
        json={"position_id": position["id"]},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["position"] == "Software Engineer"
    assert updated.json()["position_id"] == position["id"]

    _user, linked = _create_linked_employee(
        db_session,
        email="viewer.org@test.com",
        password="emppass123",
        department_id=department["id"],
        position_id=position["id"],
        position="Software Engineer",
    )
    me = client.get(
        "/api/v1/me/organization",
        headers=auth_header(client, "viewer.org@test.com", "emppass123"),
    )
    assert me.status_code == 200, me.text
    assert me.json()["position"]["title"] == "Software Engineer"
    assert me.json()["employee"]["employee_id"] == linked.id


def test_employee_cannot_modify_own_position_or_manager(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="SalesOrg")
    position = client.post(
        "/api/v1/positions",
        json={"title": "Account Exec"},
        headers=headers,
    ).json()
    _user, employee = _create_linked_employee(
        db_session,
        email="locked.org@test.com",
        password="emppass123",
        department_id=department["id"],
        position_id=position["id"],
        position="Account Exec",
    )
    emp_headers = auth_header(client, "locked.org@test.com", "emppass123")
    assert (
        client.patch(
            f"/api/v1/employees/{employee.id}",
            json={"position_id": position["id"]},
            headers=emp_headers,
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/employees/{employee.id}",
            json={"manager_id": None},
            headers=emp_headers,
        ).status_code
        == 403
    )


def test_assign_manager_and_prevent_self_and_cycles(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="HierOrg")
    ceo = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Chris",
            "last_name": "Exec",
            "email": "ceo.org@test.com",
            "phone": "+216 20 100 100",
            "department_id": department["id"],
            "position": "Chief Executive",
            "hire_date": "2020-01-01",
        },
        headers=headers,
    ).json()
    cto = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Taylor",
            "last_name": "Tech",
            "email": "cto.org@test.com",
            "phone": "+216 20 100 101",
            "department_id": department["id"],
            "position": "Chief Technology",
            "hire_date": "2021-01-01",
            "manager_id": ceo["id"],
        },
        headers=headers,
    ).json()
    engineer = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Eden",
            "last_name": "Eng",
            "email": "eng.org@test.com",
            "phone": "+216 20 100 102",
            "department_id": department["id"],
            "position": "Engineer Role",
            "hire_date": "2022-01-01",
            "manager_id": cto["id"],
        },
        headers=headers,
    ).json()

    assert engineer["manager_id"] == cto["id"]
    assert cto["manager_id"] == ceo["id"]
    assert ceo["manager_id"] is None

    self_mgr = client.patch(
        f"/api/v1/employees/{ceo['id']}",
        json={"manager_id": ceo["id"]},
        headers=headers,
    )
    assert self_mgr.status_code == 400
    assert "themselves" in self_mgr.json()["detail"].lower()

    cycle = client.patch(
        f"/api/v1/employees/{ceo['id']}",
        json={"manager_id": engineer["id"]},
        headers=headers,
    )
    assert cycle.status_code == 400
    assert "circular" in cycle.json()["detail"].lower()

    clear = client.patch(
        f"/api/v1/employees/{cto['id']}",
        json={"manager_id": None},
        headers=headers,
    )
    assert clear.status_code == 200
    assert clear.json()["manager_id"] is None


def test_hierarchy_and_directory_access(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="DirOrg")
    root = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Root",
            "last_name": "One",
            "email": "root.org@test.com",
            "phone": "+216 20 200 200",
            "department_id": department["id"],
            "position": "General Manager",
            "hire_date": "2019-01-01",
        },
        headers=headers,
    ).json()
    child = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Child",
            "last_name": "Two",
            "email": "child.org@test.com",
            "phone": "+216 20 200 201",
            "department_id": department["id"],
            "position": "Team Lead",
            "hire_date": "2020-01-01",
            "manager_id": root["id"],
        },
        headers=headers,
    ).json()
    client.post(
        "/api/v1/employees",
        json={
            "first_name": "Leaf",
            "last_name": "Three",
            "email": "leaf.org@test.com",
            "phone": "+216 20 200 202",
            "department_id": department["id"],
            "position": "Contributor",
            "hire_date": "2021-01-01",
            "manager_id": child["id"],
        },
        headers=headers,
    )

    hierarchy = client.get("/api/v1/organization/hierarchy", headers=headers)
    assert hierarchy.status_code == 200, hierarchy.text
    tree = hierarchy.json()["employees"]
    root_node = next(item for item in tree if item["employee_id"] == root["id"])
    assert root_node["children"][0]["employee_id"] == child["id"]
    assert root_node["children"][0]["children"][0]["name"] == "Leaf Three"
    assert "email" not in root_node

    directory = client.get("/api/v1/organization/directory?q=Leaf", headers=headers)
    assert directory.status_code == 200
    assert directory.json()["total"] >= 1
    assert directory.json()["items"][0]["full_name"] == "Leaf Three"

    _user, _emp = _create_linked_employee(
        db_session,
        email="dir.viewer@test.com",
        password="emppass123",
        department_id=department["id"],
        position="Viewer",
        manager_id=root["id"],
    )
    emp_headers = auth_header(client, "dir.viewer@test.com", "emppass123")
    assert client.get("/api/v1/organization/hierarchy", headers=emp_headers).status_code == 200
    assert client.get("/api/v1/organization/directory", headers=emp_headers).status_code == 200

    org = client.get(f"/api/v1/employees/{child['id']}/organization", headers=headers)
    assert org.status_code == 200
    assert org.json()["manager"]["employee_id"] == root["id"]

    assert (
        client.get(
            f"/api/v1/employees/{child['id']}/organization",
            headers=emp_headers,
        ).status_code
        == 403
    )


def test_org_position_independent_from_app_roles(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="RoleOrg")
    position = client.post(
        "/api/v1/positions",
        json={"title": "Engineering Manager Title"},
        headers=headers,
    ).json()
    create_user_with_role(
        db_session,
        email="mgr.role@test.com",
        password="mgrpass123",
        role_name="manager",
    )
    # Application role "manager" still cannot write org structure
    mgr_headers = auth_header(client, "mgr.role@test.com", "mgrpass123")
    assert (
        client.post(
            "/api/v1/positions",
            json={"title": "Blocked"},
            headers=mgr_headers,
        ).status_code
        == 403
    )
    employee = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Pat",
            "last_name": "Lead",
            "email": "pat.lead@test.com",
            "phone": "+216 20 300 300",
            "department_id": department["id"],
            "position_id": position["id"],
            "hire_date": "2023-01-01",
        },
        headers=headers,
    ).json()
    assert employee["position"] == "Engineering Manager Title"
    # Department CRUD still works
    assert create_department(client, name="StillWorks", headers=headers)["name"] == "StillWorks"


def test_manager_must_be_active_employee(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="ActiveMgrOrg")

    active_mgr = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Active",
            "last_name": "Boss",
            "email": "active.boss@test.com",
            "phone": "+216 20 400 100",
            "department_id": department["id"],
            "position": "Director",
            "hire_date": "2020-01-01",
        },
        headers=headers,
    )
    assert active_mgr.status_code == 201
    active_mgr = active_mgr.json()

    inactive_mgr = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Inactive",
            "last_name": "Boss",
            "email": "inactive.boss@test.com",
            "phone": "+216 20 400 101",
            "department_id": department["id"],
            "position": "Former Director",
            "hire_date": "2019-01-01",
        },
        headers=headers,
    ).json()
    deactivated = client.patch(
        f"/api/v1/employees/{inactive_mgr['id']}/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["employment_status"] == "inactive"

    # Active employee can be assigned as manager on create
    report = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Report",
            "last_name": "One",
            "email": "report.one@test.com",
            "phone": "+216 20 400 102",
            "department_id": department["id"],
            "position": "Staff",
            "hire_date": "2024-01-01",
            "manager_id": active_mgr["id"],
        },
        headers=headers,
    )
    assert report.status_code == 201
    assert report.json()["manager_id"] == active_mgr["id"]

    # Inactive employee cannot be newly assigned as manager
    blocked_create = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Report",
            "last_name": "Two",
            "email": "report.two@test.com",
            "phone": "+216 20 400 103",
            "department_id": department["id"],
            "position": "Staff",
            "hire_date": "2024-01-01",
            "manager_id": inactive_mgr["id"],
        },
        headers=headers,
    )
    assert blocked_create.status_code == 400
    assert "active" in blocked_create.json()["detail"].lower()

    blocked_update = client.patch(
        f"/api/v1/employees/{report.json()['id']}",
        json={"manager_id": inactive_mgr["id"]},
        headers=headers,
    )
    assert blocked_update.status_code == 400
    assert "active" in blocked_update.json()["detail"].lower()

    # Nonexistent manager is rejected
    missing = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Report",
            "last_name": "Three",
            "email": "report.three@test.com",
            "phone": "+216 20 400 104",
            "department_id": department["id"],
            "position": "Staff",
            "hire_date": "2024-01-01",
            "manager_id": 999999,
        },
        headers=headers,
    )
    assert missing.status_code == 404

    # Self as manager rejected (permissions unchanged: HR gets 400 not 403)
    self_mgr = client.patch(
        f"/api/v1/employees/{active_mgr['id']}",
        json={"manager_id": active_mgr["id"]},
        headers=headers,
    )
    assert self_mgr.status_code == 400
    assert "themselves" in self_mgr.json()["detail"].lower()

    # Active manager reassignment still works for HR
    peer = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Peer",
            "last_name": "Lead",
            "email": "peer.lead@test.com",
            "phone": "+216 20 400 105",
            "department_id": department["id"],
            "position": "Lead",
            "hire_date": "2021-01-01",
        },
        headers=headers,
    ).json()
    reassign = client.patch(
        f"/api/v1/employees/{report.json()['id']}",
        json={"manager_id": peer["id"]},
        headers=headers,
    )
    assert reassign.status_code == 200
    assert reassign.json()["manager_id"] == peer["id"]


def test_historical_inactive_manager_relationship_preserved(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="HistMgrOrg")

    manager = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Was",
            "last_name": "Manager",
            "email": "was.manager@test.com",
            "phone": "+216 20 500 100",
            "department_id": department["id"],
            "position": "Manager",
            "hire_date": "2018-01-01",
        },
        headers=headers,
    ).json()
    report = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Kept",
            "last_name": "Report",
            "email": "kept.report@test.com",
            "phone": "+216 20 500 101",
            "department_id": department["id"],
            "position": "Staff",
            "hire_date": "2022-01-01",
            "manager_id": manager["id"],
        },
        headers=headers,
    ).json()
    assert report["manager_id"] == manager["id"]

    assert (
        client.patch(
            f"/api/v1/employees/{manager['id']}/deactivate",
            headers=headers,
        ).status_code
        == 200
    )

    # Existing relationship still readable / updateable with same manager_id
    same = client.patch(
        f"/api/v1/employees/{report['id']}",
        json={"manager_id": manager["id"], "position": "Senior Staff"},
        headers=headers,
    )
    assert same.status_code == 200
    assert same.json()["manager_id"] == manager["id"]
    assert same.json()["position"] == "Senior Staff"

    # Other field update without changing manager also works
    phone_only = client.patch(
        f"/api/v1/employees/{report['id']}",
        json={"phone": "+216 20 500 199"},
        headers=headers,
    )
    assert phone_only.status_code == 200
    assert phone_only.json()["manager_id"] == manager["id"]
