"""Security: unified Offboarding availability + tool auth remain authoritative."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.core.context.models import AIExecutionContext
from app.ai.registry import OFFBOARDING_AGENT, get_available_agents, is_agent_available
from app.ai.routing import route_message
from app.ai.tools.authorization import authorize_tool
from app.ai.tools.exceptions import ToolAuthorizationError, ToolExecutionError
from app.ai.tools.offboarding_reads import (
    FindEmployeesForOffboardingInput,
    FindEmployeesForOffboardingTool,
    GetOffboardingCaseInput,
    GetOffboardingCaseTool,
)
from app.modules.offboarding.models import OffboardingReason, OffboardingStatus


def _ctx(
    *,
    role_names: frozenset[str],
    permission_names: frozenset[str],
    employee_id: int | None,
    candidate_id: int | None = None,
    user_id: int = 1,
) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=role_names,
        permission_names=permission_names,
        employee_id=employee_id,
        candidate_id=candidate_id,
    )


def _case(*, case_id: int = 4, employee_id: int = 99):
    return SimpleNamespace(
        id=case_id,
        employee_id=employee_id,
        reason=OffboardingReason.RESIGNATION,
        reason_details="Personal",
        last_working_day=date(2026, 12, 1),
        status=OffboardingStatus.PENDING_CLEARANCE,
        initiated_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=None,
        employee=SimpleNamespace(full_name="Sam Staff"),
    )


def test_employee_self_scope_available_and_routes():
    ctx = _ctx(
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
    )
    assert is_agent_available(OFFBOARDING_AGENT, ctx) is True
    available = get_available_agents(ctx)
    decision = route_message("What is my offboarding status?", available)
    assert decision.kind == "agent"
    assert decision.agent_id == "offboarding"


def test_employee_cross_employee_case_denial():
    """Employee can invoke the agent; other employees' case_ids are denied in tools."""
    ctx = _ctx(
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
        user_id=9,
    )
    service = MagicMock()
    service.list_for_user.return_value = [_case(case_id=4, employee_id=99)]
    tool = GetOffboardingCaseTool(service)
    with pytest.raises(ToolExecutionError, match="not found"):
        tool.execute(ctx, GetOffboardingCaseInput(case_id=999))


def test_hr_access_available_and_routes():
    ctx = _ctx(
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"offboarding:read"}),
        employee_id=None,
    )
    assert is_agent_available(OFFBOARDING_AGENT, ctx) is True
    available = get_available_agents(ctx)
    decision = route_message("What is Sarah's offboarding status?", available)
    assert decision.kind == "agent"
    assert decision.agent_id == "offboarding"
    tool = FindEmployeesForOffboardingTool(employee_service=MagicMock())
    authorize_tool(tool, ctx, FindEmployeesForOffboardingInput(q="Sarah"))


def test_unauthorized_manager_without_employee_id_unavailable():
    ctx = _ctx(
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"leaves:read", "offboarding:read"}),
        employee_id=None,
    )
    assert is_agent_available(OFFBOARDING_AGENT, ctx) is False
    available = get_available_agents(ctx)
    decision = route_message("What is Sarah's offboarding status?", available)
    assert decision.kind == "unavailable"
    assert "offboarding" in (decision.reason or "")


def test_manager_with_employee_id_cannot_use_hr_lookup_tool():
    """Manager may see self agent via employee_id; HR-only lookup still denies."""
    ctx = _ctx(
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=50,
        user_id=5,
    )
    assert is_agent_available(OFFBOARDING_AGENT, ctx) is True
    tool = FindEmployeesForOffboardingTool(employee_service=MagicMock())
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(tool, ctx, FindEmployeesForOffboardingInput(q="Sarah"))


def test_candidate_denial():
    ctx = _ctx(
        role_names=frozenset({"candidate"}),
        permission_names=frozenset(),
        employee_id=None,
        candidate_id=80,
        user_id=8,
    )
    assert is_agent_available(OFFBOARDING_AGENT, ctx) is False
    available = get_available_agents(ctx)
    decision = route_message("What is Sarah's offboarding status?", available)
    assert decision.kind == "unavailable"
