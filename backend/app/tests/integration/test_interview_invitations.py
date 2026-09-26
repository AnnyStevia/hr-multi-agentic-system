from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.identity.models import User
from app.modules.interviews.models import Interview, InterviewInterviewer, InterviewSlot, InterviewStatus
from app.modules.notifications.models import Notification, NotificationType
from app.tests.helpers import auth_header, create_candidate_user, create_department, create_user_with_role
from app.tests.integration.test_application_review import _hr_headers, _submit_application


def _shortlist(client, db_session, application_id: int):
    headers = _hr_headers(client, db_session)
    assert (
        client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "screening"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "shortlisted"},
            headers=headers,
        ).status_code
        == 200
    )
    return headers


def _future_slots(count: int = 3):
    base = datetime.now(UTC) + timedelta(days=3)
    hours = [10, 14, 11, 15, 16, 9]
    slots = []
    for day_offset in range(count):
        hour = hours[day_offset % len(hours)]
        start = base.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
        end = start + timedelta(minutes=30)
        slots.append({"starts_at": start.isoformat(), "ends_at": end.isoformat()})
    return slots


def _create_panel_employees(client, count: int = 1, *, headers=None) -> list[int]:
    auth = headers or auth_header(client)
    dept = create_department(client, name="Interview Panel", headers=auth)
    ids: list[int] = []
    for _ in range(count):
        suffix = uuid4().hex[:8]
        response = client.post(
            "/api/v1/employees",
            json={
                "first_name": "Panel",
                "last_name": f"Member{suffix}",
                "email": f"panel.{suffix}@test.com",
                "phone": f"+2162{int(suffix[:7], 16) % 10_000_000:07d}",
                "department_id": dept["id"],
                "position": "Engineer",
                "hire_date": "2024-01-15",
            },
            headers=auth,
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


def _invite_payload(client=None, interviewer_employee_ids=None, **overrides):
    ids = interviewer_employee_ids
    if ids is None:
        assert client is not None, "client required when interviewer_employee_ids omitted"
        ids = _create_panel_employees(client)
    payload = {
        "message": "We would like to meet you.",
        "slots": _future_slots(),
        "interviewer_employee_ids": ids,
    }
    payload.update(overrides)
    return payload


def _shortlist_with_headers(client, application_id: int, headers: dict):
    assert (
        client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "screening"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "shortlisted"},
            headers=headers,
        ).status_code
        == 200
    )


def _create_invitation(client, db_session, application_id: int, headers=None):
    if headers is None:
        headers = _shortlist(client, db_session, application_id)
    else:
        _shortlist_with_headers(client, application_id, headers)
    response = client.post(
        f"/api/v1/interviews/applications/{application_id}",
        json=_invite_payload(client),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json(), headers


def test_hr_can_create_interview_invitation_for_shortlisted_application(client, db_session):
    application, job, candidate_headers, _storage = _submit_application(client, db_session)
    data, _headers = _create_invitation(client, db_session, application["id"])

    assert data["application_id"] == application["id"]
    assert data["status"] == "proposed"
    assert data["job_title"] == job["title"]
    assert len(data["slots"]) == 3
    assert all(slot["is_available"] for slot in data["slots"])
    assert len(data["interviewers"]) == 1
    assert data["interviewer_name"] == data["interviewers"][0]["full_name"]

    assignments = (
        db_session.query(InterviewInterviewer)
        .filter(InterviewInterviewer.interview_id == data["id"])
        .all()
    )
    assert len(assignments) == 1
    assert assignments[0].employee_id == data["interviewers"][0]["employee_id"]

    notification = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.INTERVIEW_INVITATION,
            Notification.related_entity_id == data["id"],
        )
        .one()
    )
    assert notification.related_entity_type == "interview"

    listing = client.get("/api/v1/notifications", headers=candidate_headers)
    assert any(item["type"] == "interview_invitation" for item in listing.json())


def test_non_authorized_user_cannot_create_invitation(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(client, db_session)
    _shortlist(client, db_session, application["id"])

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(client),
        headers=candidate_headers,
    )
    assert response.status_code == 403


def test_cannot_create_invitation_for_non_shortlisted_application(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _hr_headers(client, db_session)

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(client),
        headers=headers,
    )
    assert response.status_code == 400


def test_slot_count_must_be_between_two_and_five(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _shortlist(client, db_session, application["id"])
    panel = _create_panel_employees(client)

    too_few = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json={"message": "Hello", "slots": _future_slots(1), "interviewer_employee_ids": panel},
        headers=headers,
    )
    assert too_few.status_code in (400, 422)

    too_many = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json={"message": "Hello", "slots": _future_slots(6), "interviewer_employee_ids": panel},
        headers=headers,
    )
    assert too_many.status_code in (400, 422)

    exactly_two = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json={"message": "Hello", "slots": _future_slots(2), "interviewer_employee_ids": panel},
        headers=headers,
    )
    assert exactly_two.status_code == 201, exactly_two.text
    assert len(exactly_two.json()["slots"]) == 2


def test_duplicate_slots_are_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _shortlist(client, db_session, application["id"])
    slots = _future_slots()
    duplicate = [slots[0], slots[0], slots[1]]

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json={"message": "Hello", "slots": duplicate, "interviewer_employee_ids": _create_panel_employees(client)},
        headers=headers,
    )
    assert response.status_code == 400


def test_past_slots_are_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _shortlist(client, db_session, application["id"])
    past = datetime.now(UTC) - timedelta(days=1)
    end = past + timedelta(minutes=30)
    slots = [
        {"starts_at": past.isoformat(), "ends_at": end.isoformat()},
        *_future_slots()[:2],
    ]

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json={"message": "Hello", "slots": slots, "interviewer_employee_ids": _create_panel_employees(client)},
        headers=headers,
    )
    assert response.status_code == 400


def test_invalid_time_ranges_are_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _shortlist(client, db_session, application["id"])
    slots = _future_slots()
    slots[0]["ends_at"] = slots[0]["starts_at"]

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json={"message": "Hello", "slots": slots, "interviewer_employee_ids": _create_panel_employees(client)},
        headers=headers,
    )
    assert response.status_code == 400


def test_cannot_create_second_invitation_while_waiting_for_response(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    _interview, headers = _create_invitation(client, db_session, application["id"])

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(client),
        headers=headers,
    )
    assert response.status_code == 409


def test_cannot_create_second_invitation_after_candidate_confirms(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.duplicate.scheduled@test.com",
    )
    interview, headers = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][0]["id"]

    confirmed = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": slot_id},
        headers=candidate_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "scheduled"

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(client),
        headers=headers,
    )
    assert response.status_code == 409


def test_hr_list_shows_waiting_status_label(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    _data, headers = _create_invitation(client, db_session, application["id"])

    listing = client.get(f"/api/v1/interviews/applications/{application['id']}", headers=headers)
    assert listing.status_code == 200
    item = listing.json()[0]
    assert item["status"] == "proposed"
    assert "waiting for candidate" in item["status_label"].lower()


def test_candidate_can_view_and_confirm_own_interview(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.confirm@test.com",
    )
    interview, _headers = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][1]["id"]

    detail = client.get(f"/api/v1/careers/interviews/{interview['id']}", headers=candidate_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "proposed"
    assert len(detail.json()["slots"]) == 3

    confirmed = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": slot_id},
        headers=candidate_headers,
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "scheduled"
    assert body["selected_slot"]["id"] == slot_id
    assert len(body["slots"]) == 1

    slots = db_session.query(InterviewSlot).filter(InterviewSlot.interview_id == interview["id"]).all()
    selected = next(slot for slot in slots if slot.id == slot_id)
    others = [slot for slot in slots if slot.id != slot_id]
    assert selected.is_selected is True
    assert all(not slot.is_available for slot in others)


def test_hr_receives_notification_when_candidate_confirms(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.hr.notif@test.com",
    )
    interview, headers = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][0]["id"]

    confirmed = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": slot_id},
        headers=candidate_headers,
    )
    assert confirmed.status_code == 200

    hr_user = db_session.query(User).filter(User.email == "hr.review@test.com").one()
    hr_notifications = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == hr_user.id,
            Notification.type == NotificationType.INTERVIEW_SCHEDULED,
        )
        .all()
    )
    assert len(hr_notifications) == 1
    assert hr_notifications[0].related_entity_id == interview["id"]

    listing = client.get("/api/v1/notifications", headers=headers)
    assert any(item["type"] == "interview_scheduled" for item in listing.json())


def test_candidate_cannot_access_other_candidates_interview(client, db_session):
    application, _job, _first_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.owner@test.com",
    )
    interview, _headers = _create_invitation(client, db_session, application["id"])

    create_candidate_user(db_session, email="interview.other@test.com", password="candidate123")
    other_headers = auth_header(client, "interview.other@test.com", "candidate123")

    assert client.get(f"/api/v1/careers/interviews/{interview['id']}", headers=other_headers).status_code == 404


def test_candidate_cannot_confirm_twice(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.twice@test.com",
    )
    interview, _headers = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][0]["id"]

    first = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": slot_id},
        headers=candidate_headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": interview["slots"][1]["id"]},
        headers=candidate_headers,
    )
    assert second.status_code == 400


def test_candidate_cannot_confirm_slot_from_another_interview(client, db_session):
    application_a, _job, candidate_a_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.a@test.com",
    )
    application_b, _job_b, candidate_b_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.b@test.com",
    )
    interview_a, headers = _create_invitation(client, db_session, application_a["id"])
    interview_b, _headers = _create_invitation(client, db_session, application_b["id"], headers=headers)

    response = client.post(
        f"/api/v1/careers/interviews/{interview_a['id']}/confirm",
        json={"slot_id": interview_b["slots"][0]["id"]},
        headers=candidate_a_headers,
    )
    assert response.status_code == 404


def test_unauthenticated_cannot_access_interviews(client):
    assert client.get("/api/v1/careers/interviews/1").status_code == 401
    assert client.post("/api/v1/careers/interviews/1/confirm", json={"slot_id": 1}).status_code == 401


def test_legacy_partial_confirm_is_repaired_on_read(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="interview.legacy@test.com",
    )
    interview, headers = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][1]["id"]

    from app.modules.interviews.models import Interview

    row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    row.selected_slot_id = slot_id
    row.status = InterviewStatus.PROPOSED
    for slot in row.slots:
        slot.is_selected = slot.id == slot_id
        slot.is_available = True
    db_session.commit()

    listing = client.get(f"/api/v1/interviews/applications/{application['id']}", headers=headers)
    assert listing.status_code == 200
    item = listing.json()[0]
    assert item["status"] == "scheduled"
    assert item["selected_slot"]["id"] == slot_id

    detail = client.get(f"/api/v1/careers/interviews/{interview['id']}", headers=candidate_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "scheduled"
    assert detail.json()["selected_slot"]["id"] == slot_id


def test_create_with_multiple_interviewers(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.multi.panel@test.com"
    )
    headers = _shortlist(client, db_session, application["id"])
    panel = _create_panel_employees(client, 2)

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(interviewer_employee_ids=panel),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["interviewers"]) == 2
    assert {item["employee_id"] for item in body["interviewers"]} == set(panel)
    assert body["interviewer_name"] == body["interviewers"][0]["full_name"]

    row = db_session.query(Interview).filter(Interview.id == body["id"]).one()
    assert row.interviewer_employee_id == panel[0]
    assert db_session.query(InterviewInterviewer).filter(
        InterviewInterviewer.interview_id == body["id"]
    ).count() == 2


def test_duplicate_interviewer_ids_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.dup.panel@test.com"
    )
    headers = _shortlist(client, db_session, application["id"])
    panel = _create_panel_employees(client, 1)

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(interviewer_employee_ids=[panel[0], panel[0]]),
        headers=headers,
    )
    assert response.status_code == 400
    assert db_session.query(Interview).filter(Interview.application_id == application["id"]).count() == 0


def test_nonexistent_interviewer_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.missing.panel@test.com"
    )
    headers = _shortlist(client, db_session, application["id"])

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(interviewer_employee_ids=[999999]),
        headers=headers,
    )
    assert response.status_code == 404
    assert db_session.query(Interview).filter(Interview.application_id == application["id"]).count() == 0


def test_inactive_employee_interviewer_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.inactive.emp@test.com"
    )
    headers = _shortlist(client, db_session, application["id"])
    panel = _create_panel_employees(client, 1)
    employee = db_session.query(Employee).filter(Employee.id == panel[0]).one()
    employee.employment_status = EmploymentStatus.INACTIVE
    db_session.commit()

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(interviewer_employee_ids=panel),
        headers=headers,
    )
    assert response.status_code == 400
    assert db_session.query(Interview).filter(Interview.application_id == application["id"]).count() == 0


def test_inactive_user_interviewer_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.inactive.user@test.com"
    )
    headers = _shortlist(client, db_session, application["id"])
    dept = create_department(client, name="Inactive User Panel")
    linked = create_user_with_role(
        db_session,
        email="inactive.panelist@test.com",
        password="panelpass123",
        role_name="employee",
        is_active=False,
    )
    employee = Employee(
        employee_number="PENDING",
        first_name="Inactive",
        last_name="Panelist",
        email="inactive.panelist@test.com",
        phone="+21620999001",
        department_id=dept["id"],
        position="Engineer",
        hire_date=datetime.now(UTC).date(),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=linked.id,
    )
    db_session.add(employee)
    db_session.flush()
    employee.employee_number = f"EMP-{employee.id:06d}"
    db_session.commit()

    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(interviewer_employee_ids=[employee.id]),
        headers=headers,
    )
    assert response.status_code == 400
    assert db_session.query(Interview).filter(Interview.application_id == application["id"]).count() == 0


def test_nonexistent_application_invite_returns_404(client, db_session):
    headers = _hr_headers(client, db_session)
    response = client.post(
        "/api/v1/interviews/applications/999999",
        json=_invite_payload(client),
        headers=headers,
    )
    assert response.status_code == 404


def test_employee_cannot_create_interview_invitation(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.emp.create@test.com"
    )
    _shortlist(client, db_session, application["id"])
    create_user_with_role(
        db_session,
        email="employee.invite@test.com",
        password="emppass123",
        role_name="employee",
    )
    emp_headers = auth_header(client, "employee.invite@test.com", "emppass123")
    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(client),
        headers=emp_headers,
    )
    assert response.status_code == 403


def test_get_interview_includes_interviewers(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.get.panel@test.com"
    )
    interview, headers = _create_invitation(client, db_session, application["id"])

    detail = client.get(f"/api/v1/interviews/{interview['id']}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["interviewers"]) == 1

    listing = client.get(f"/api/v1/interviews/applications/{application['id']}", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()[0]["interviewers"]) == 1


def test_naive_slot_datetimes_are_accepted_as_utc(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="interview.naive.slots@test.com"
    )
    headers = _shortlist(client, db_session, application["id"])
    base = (datetime.now(UTC) + timedelta(days=4)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    slots = [
        {
            "starts_at": base.replace(hour=10, minute=0).isoformat(),
            "ends_at": base.replace(hour=10, minute=30).isoformat(),
        },
        {
            "starts_at": base.replace(hour=14, minute=0).isoformat(),
            "ends_at": base.replace(hour=14, minute=30).isoformat(),
        },
    ]
    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(client, slots=slots),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["slots"]) == 2
