"""Live Gemini + Postgres smoke for get_my_leave_balance (skipped without API key)."""

from datetime import UTC, datetime

import pytest

from app.ai.core.config import ai_settings
from app.ai.core.config.settings import AISettings
from app.ai.core.context import build_ai_execution_context
from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.orchestration import run_controlled_leave_balance_smoke
from app.ai.tools import GetMyLeaveBalanceTool, ToolRegistry
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.service import AuthService
from app.modules.leave.repository import LeaveRepository
from app.modules.leave.schemas import LeavePolicyCreateRequest, LeaveTypeCreateRequest
from app.modules.leave.service import LeaveService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.tests.helpers import create_user_with_role
from app.tests.unit.test_ai_context import _department_id, _link_employee

_HAS_GEMINI = bool(ai_settings.gemini_api_key.strip())

pytestmark = pytest.mark.skipif(
    not _HAS_GEMINI,
    reason="GEMINI_API_KEY not configured",
)

_INPUT_USD_PER_M = 0.75
_OUTPUT_USD_PER_M = 3.75


def _leave_service(db_session) -> LeaveService:
    return LeaveService(
        LeaveRepository(db_session),
        EmployeeRepository(db_session),
        NotificationService(NotificationRepository(db_session)),
    )


def _approx_cost_usd(usage) -> float | None:
    if usage is None:
        return None
    input_tokens = usage.input_tokens or 0
    output_tokens = (usage.output_tokens or 0) + (usage.thinking_tokens or 0)
    return (input_tokens / 1_000_000) * _INPUT_USD_PER_M + (
        output_tokens / 1_000_000
    ) * _OUTPUT_USD_PER_M


def test_live_gemini_get_my_leave_balance(client, db_session):
    del client  # DB fixtures only; HTTP client unused
    year = datetime.now(UTC).year
    user = create_user_with_role(
        db_session,
        email="ai.leave.balance.live@test.com",
        password="emppass123",
        role_name="employee",
    )
    employee = _link_employee(
        db_session,
        user,
        department_id=_department_id(db_session),
        email=user.email,
    )
    service = _leave_service(db_session)
    leave_type = service.create_type(
        LeaveTypeCreateRequest(
            name=f"AI Smoke Leave {year}",
            description="Live Gemini leave balance smoke",
            is_paid=True,
        )
    )
    service.create_policy(
        LeavePolicyCreateRequest(
            leave_type_id=leave_type.id,
            year=year,
            days_allowed=18,
        )
    )

    reloaded = AuthService(db_session).get_user_by_id(user.id)
    assert reloaded is not None
    context = build_ai_execution_context(
        reloaded,
        employees=EmployeeRepository(db_session),
    )
    assert context.employee_id == employee.id
    assert "leaves:read" in context.permission_names

    expected = service.get_balances(employee.id)
    assert expected
    assert expected[0].days_allowed == 18

    registry = ToolRegistry()
    registry.register(GetMyLeaveBalanceTool(service))
    settings = AISettings(
        ai_llm_provider="gemini",
        gemini_api_key=ai_settings.gemini_api_key,
        gemini_model=ai_settings.gemini_model or "gemini-3.8-flash",
    )
    provider = get_llm_provider(settings)

    try:
        result = run_controlled_leave_balance_smoke(
            provider=provider,
            context=context,
            registry=registry,
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if any(
            token in message
            for token in (
                "429",
                "rate",
                "quota",
                "resource_exhausted",
                "billing",
                "insufficient",
            )
        ):
            pytest.skip(f"Gemini rate/quota/billing issue: {exc}")
        raise

    assert result.tool_names_called == ("get_my_leave_balance",)
    assert len(result.tool_results) == 1
    data = result.tool_results[0].data
    assert data is not None
    assert data["employee_id"] == employee.id
    assert data["year"] == year
    assert data["balances"][0]["leave_type_name"] == leave_type.name
    assert data["balances"][0]["days_allowed"] == 18
    assert data["balances"][0]["days_available"] == 18
    assert result.final_content.strip()

    usage = result.usage
    cost = _approx_cost_usd(usage)
    print(f"Gemini model used: {result.model}")
    print("Thinking level: low")
    if usage is not None:
        print(
            "Token usage:"
            f" input={usage.input_tokens}"
            f" output={usage.output_tokens}"
            f" thinking={usage.thinking_tokens}"
            f" total={usage.total_tokens}"
        )
    print(f"Approximate cost USD: {cost}")
    print(f"Final response: {result.final_content[:240]}")
