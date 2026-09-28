"""Unit tests: agent registry availability (permission-based only)."""

from __future__ import annotations

from app.ai.core.context.models import AIExecutionContext
from app.ai.registry import (
    REGISTERED_AGENTS,
    get_available_agents,
    list_registered_agents,
)


def _ctx(
    *,
    permission_names: frozenset[str],
    role_names: frozenset[str] = frozenset(),
    user_id: int = 1,
    employee_id: int | None = 10,
    candidate_id: int | None = None,
) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=role_names,
        permission_names=permission_names,
        employee_id=employee_id,
        candidate_id=candidate_id,
    )


def test_four_implemented_agents_registered():
    ids = {a.id for a in list_registered_agents()}
    assert ids == {"knowledge", "leave", "recruitment", "onboarding"}
    assert len(REGISTERED_AGENTS) == 4
    assert "training" not in ids
    assert "documents" not in ids
    assert "offboarding" not in ids


def test_employee_available_agents_include_onboarding():
    # Employees lack onboarding:read; availability uses employee_id.
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(
                {
                    "company_documents:read",
                    "leaves:read",
                    "leaves:write",
                    "employees:read",
                }
            ),
            role_names=frozenset({"employee"}),
        )
    )
    assert {a.id for a in available} == {"knowledge", "leave", "onboarding"}


def test_manager_available_agents_no_recruitment_includes_onboarding():
    # Manager RBAC role may exist but recruitment:read is revoked.
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(
                {
                    "company_documents:read",
                    "leaves:read",
                    "leaves:write",
                    "employees:read",
                }
            ),
            role_names=frozenset({"manager"}),
        )
    )
    assert {a.id for a in available} == {"knowledge", "leave", "onboarding"}
    assert all(a.id != "recruitment" for a in available)


def test_leave_available_without_manager_role():
    """Leave availability is permission-based; manager role is not required."""
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"leaves:read"}),
            role_names=frozenset({"employee"}),
        )
    )
    assert {a.id for a in available} == {"leave", "onboarding"}


def test_hr_available_agents_include_recruitment_and_onboarding():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(
                {
                    "company_documents:read",
                    "leaves:read",
                    "recruitment:read",
                    "recruitment:write",
                }
            ),
            role_names=frozenset({"hr"}),
        )
    )
    assert {a.id for a in available} == {
        "knowledge",
        "leave",
        "recruitment",
        "onboarding",
    }


def test_admin_available_agents_include_recruitment_and_onboarding():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(
                {
                    "company_documents:read",
                    "leaves:read",
                    "recruitment:read",
                }
            ),
            role_names=frozenset({"admin"}),
        )
    )
    assert {a.id for a in available} == {
        "knowledge",
        "leave",
        "recruitment",
        "onboarding",
    }


def test_recruitment_unavailable_without_permission():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(
                {"company_documents:read", "leaves:read"}
            ),
            role_names=frozenset({"hr"}),  # role alone must not grant recruitment
        )
    )
    assert "recruitment" not in {a.id for a in available}


def test_candidate_typically_no_agents():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(),
            role_names=frozenset({"candidate"}),
            employee_id=None,
            candidate_id=1,
        )
    )
    assert available == ()


def test_onboarding_available_via_employee_id_without_permission():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"leaves:read"}),
            role_names=frozenset({"employee"}),
            employee_id=42,
        )
    )
    assert "onboarding" in {a.id for a in available}


def test_onboarding_available_via_permission_without_employee_id():
    """HR path: onboarding:read grants availability even without employee_id."""
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"onboarding:read"}),
            role_names=frozenset({"hr"}),
            employee_id=None,
        )
    )
    assert {a.id for a in available} == {"onboarding"}


def test_candidate_no_employee_id_no_onboarding_read_unavailable():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(),
            role_names=frozenset({"candidate"}),
            employee_id=None,
            candidate_id=99,
        )
    )
    assert "onboarding" not in {a.id for a in available}
    assert available == ()
