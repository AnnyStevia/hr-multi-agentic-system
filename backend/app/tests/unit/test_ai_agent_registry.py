"""Unit tests: agent registry availability (permission-based only)."""

from __future__ import annotations

from app.ai.core.context.models import AIExecutionContext
from app.ai.registry import (
    DOCUMENTS_AGENT,
    OFFBOARDING_AGENT,
    REGISTERED_AGENTS,
    TRAINING_AGENT,
    get_agent_definition,
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


def test_seven_implemented_agents_registered():
    ids = {a.id for a in list_registered_agents()}
    assert ids == {
        "knowledge",
        "leave",
        "recruitment",
        "onboarding",
        "training",
        "documents",
        "offboarding",
    }
    assert len(REGISTERED_AGENTS) == 7
    training = get_agent_definition("training")
    assert training is TRAINING_AGENT
    assert training.supports_confirmation is True
    assert training.id == "training"
    assert training.display_name == "Training Agent"
    documents = get_agent_definition("documents")
    assert documents is DOCUMENTS_AGENT
    assert documents.supports_confirmation is False
    assert documents.id == "documents"
    assert documents.display_name == "Document Agent"
    offboarding = get_agent_definition("offboarding")
    assert offboarding is OFFBOARDING_AGENT
    assert offboarding.supports_confirmation is True
    assert offboarding.id == "offboarding"
    assert offboarding.display_name == "Offboarding Agent"


def test_employee_available_agents_include_onboarding_and_training():
    # Employees lack onboarding:read; availability uses employee_id.
    # Training uses employee_id (not bare training:read).
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
    assert {a.id for a in available} == {
        "knowledge",
        "leave",
        "onboarding",
        "training",
        "documents",
        "offboarding",
    }


def test_manager_available_agents_no_recruitment_includes_training():
    # Manager RBAC role may exist but recruitment:read is revoked.
    # Offboarding available via employee_id (self only at tool layer).
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
    assert {a.id for a in available} == {
        "knowledge",
        "leave",
        "onboarding",
        "training",
        "documents",
        "offboarding",
    }
    assert all(a.id != "recruitment" for a in available)


def test_leave_available_without_manager_role():
    """Leave availability is permission-based; manager role is not required."""
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"leaves:read"}),
            role_names=frozenset({"employee"}),
        )
    )
    assert {a.id for a in available} == {
        "leave",
        "onboarding",
        "training",
        "documents",
        "offboarding",
    }


def test_hr_available_agents_include_recruitment_onboarding_training():
    # Default fixture has employee_id → Training available via employee_id.
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
        "training",
        "documents",
        "offboarding",
    }


def test_admin_available_agents_include_recruitment_onboarding_training():
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
        "training",
        "documents",
        "offboarding",
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
    assert "training" in {a.id for a in available}
    assert "offboarding" in {a.id for a in available}


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


def test_training_available_via_hr_staff_and_training_read_without_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"training:read"}),
            role_names=frozenset({"hr"}),
            employee_id=None,
        )
    )
    assert {a.id for a in available} == {"training"}


def test_training_available_via_admin_staff_and_training_read_without_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"training:read"}),
            role_names=frozenset({"admin"}),
            employee_id=None,
        )
    )
    assert {a.id for a in available} == {"training"}


def test_training_unavailable_with_training_read_alone_without_employee_or_staff():
    """Bare training:read without employee_id and without HR/Admin → unavailable."""
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"training:read"}),
            role_names=frozenset({"employee"}),
            employee_id=None,
        )
    )
    assert "training" not in {a.id for a in available}


def test_hr_staff_without_training_read_and_no_employee_id_no_training():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"onboarding:read"}),
            role_names=frozenset({"hr"}),
            employee_id=None,
        )
    )
    assert "training" not in {a.id for a in available}


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
    assert "training" not in {a.id for a in available}
    assert "documents" not in {a.id for a in available}
    assert "offboarding" not in {a.id for a in available}
    assert available == ()


def test_documents_available_via_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"leaves:read"}),
            role_names=frozenset({"employee"}),
            employee_id=42,
        )
    )
    assert "documents" in {a.id for a in available}
    assert "offboarding" in {a.id for a in available}


def test_documents_available_via_hr_staff_and_company_documents_read_without_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"company_documents:read"}),
            role_names=frozenset({"hr"}),
            employee_id=None,
        )
    )
    assert {a.id for a in available} == {"knowledge", "documents"}


def test_documents_available_via_admin_staff_and_company_documents_read_without_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"company_documents:read"}),
            role_names=frozenset({"admin"}),
            employee_id=None,
        )
    )
    assert "documents" in {a.id for a in available}


def test_documents_unavailable_with_company_documents_read_alone_without_employee_or_staff():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"company_documents:read"}),
            role_names=frozenset({"employee"}),
            employee_id=None,
        )
    )
    assert "documents" not in {a.id for a in available}
    # Knowledge still available via bare company_documents:read.
    assert "knowledge" in {a.id for a in available}


def test_offboarding_available_via_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"leaves:read"}),
            role_names=frozenset({"employee"}),
            employee_id=42,
        )
    )
    assert "offboarding" in {a.id for a in available}


def test_offboarding_available_via_hr_staff_and_offboarding_read_without_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"offboarding:read"}),
            role_names=frozenset({"hr"}),
            employee_id=None,
        )
    )
    assert {a.id for a in available} == {"offboarding"}


def test_offboarding_available_via_admin_staff_and_offboarding_read_without_employee_id():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"offboarding:read"}),
            role_names=frozenset({"admin"}),
            employee_id=None,
        )
    )
    assert "offboarding" in {a.id for a in available}


def test_offboarding_unavailable_with_offboarding_read_alone_without_employee_or_staff():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"offboarding:read"}),
            role_names=frozenset({"employee"}),
            employee_id=None,
        )
    )
    assert "offboarding" not in {a.id for a in available}


def test_manager_without_hr_staff_no_employee_id_no_offboarding():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"leaves:read", "offboarding:read"}),
            role_names=frozenset({"manager"}),
            employee_id=None,
        )
    )
    assert "offboarding" not in {a.id for a in available}


def test_candidate_no_offboarding():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset(),
            role_names=frozenset({"candidate"}),
            employee_id=None,
            candidate_id=99,
        )
    )
    assert "offboarding" not in {a.id for a in available}
    assert available == ()


def test_hr_staff_without_offboarding_read_and_no_employee_id_no_offboarding():
    available = get_available_agents(
        _ctx(
            permission_names=frozenset({"onboarding:read"}),
            role_names=frozenset({"hr"}),
            employee_id=None,
        )
    )
    assert "offboarding" not in {a.id for a in available}
