"""Unit tests for confirmation-gated Offboarding write tools."""

from __future__ import annotations

import ast
import base64
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.agents.offboarding.agent import OffboardingAgent
from app.ai.confirmation import (
    ConfirmationError,
    create_confirmation_token,
    verify_confirmation_token,
)
from app.ai.core.context import AIExecutionContext
from app.ai.tools.authorization import authorize_tool
from app.ai.tools.exceptions import ToolAuthorizationError, ToolExecutionError
from app.ai.tools.executor import ToolExecutor, _infer_target
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.offboarding_writes import (
    CompleteOffboardingCaseInput,
    CompleteOffboardingCaseTool,
    UpdateOffboardingClearanceInput,
    UpdateOffboardingClearanceTool,
    UpdateOffboardingTaskInput,
    UpdateOffboardingTaskTool,
)
from app.modules.offboarding.models import (
    OffboardingClearanceStatus,
    OffboardingStatus,
    OffboardingTaskStatus,
)
from app.modules.offboarding.schemas import OffboardingClearanceUpdateRequest
from app.shared.exceptions import AppException


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"offboarding:read", "offboarding:write"}),
        employee_id=10,
        candidate_id=None,
    )


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _manager() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=5,
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=50,
        candidate_id=None,
    )


def _candidate() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=8,
        role_names=frozenset({"candidate"}),
        permission_names=frozenset(),
        employee_id=None,
        candidate_id=80,
    )


def _actor() -> MagicMock:
    user = MagicMock()
    user.id = 1
    return user


def _registry(*tools) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_infer_target_offboarding_tools():
    assert _infer_target("complete_offboarding_case", {"case_id": 4}) == (
        "offboarding_case",
        4,
    )
    assert _infer_target(
        "update_offboarding_clearance", {"case_id": 4, "item_id": 7, "status": "cleared"}
    ) == ("offboarding_clearance_item", 7)
    assert _infer_target(
        "update_offboarding_task",
        {"operation": "start", "task_id": 12, "case_id": 4},
    ) == ("offboarding_task", 12)
    # Onboarding task_id path unchanged for other tools.
    assert _infer_target("acknowledge_onboarding_task", {"task_id": 3}) == (
        "onboarding_task",
        3,
    )


def test_complete_proposes_confirmation_without_executing():
    service = MagicMock()
    tool = CompleteOffboardingCaseTool(service)
    pending = ToolExecutor(_registry(tool)).execute(
        _hr(), "complete_offboarding_case", {"case_id": 4}
    )
    assert pending.confirmation_token
    assert pending.data["status"] == "pending_confirmation"
    service.complete.assert_not_called()


def test_complete_confirmation_executes_service():
    service = MagicMock()
    case = SimpleNamespace(
        id=4,
        employee_id=99,
        status=OffboardingStatus.COMPLETED,
        employee=SimpleNamespace(employment_status="inactive", user_id=42),
    )
    service.complete.return_value = case
    tool = CompleteOffboardingCaseTool(service)
    done = ToolExecutor(_registry(tool)).execute(
        _hr(),
        "complete_offboarding_case",
        {"case_id": 4},
        execute_writes=True,
    )
    service.complete.assert_called_once_with(4)
    assert done.data["status"] == "completed"
    assert done.data["account_deactivated"] is True
    assert done.data["employment_status"] == "inactive"


def test_complete_blockers_surface_domain_message():
    service = MagicMock()
    service.complete.side_effect = AppException(
        "Offboarding cannot be completed: clearance is incomplete",
        status_code=400,
    )
    tool = CompleteOffboardingCaseTool(service)
    with pytest.raises(ToolExecutionError, match="clearance is incomplete"):
        ToolExecutor(_registry(tool)).execute(
            _hr(),
            "complete_offboarding_case",
            {"case_id": 4},
            execute_writes=True,
        )


def test_employee_cannot_complete_or_clear_clearance():
    service = MagicMock()
    complete = CompleteOffboardingCaseTool(service)
    clearance = UpdateOffboardingClearanceTool(service, get_user=lambda _id: _actor())
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(complete, _employee(), CompleteOffboardingCaseInput(case_id=4))
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            clearance,
            _employee(),
            UpdateOffboardingClearanceInput(
                case_id=4, item_id=1, status="cleared"
            ),
        )


def test_clearance_mutation_requires_confirmation():
    service = MagicMock()
    tool = UpdateOffboardingClearanceTool(service, get_user=lambda _id: _actor())
    pending = ToolExecutor(_registry(tool)).execute(
        _hr(),
        "update_offboarding_clearance",
        {"case_id": 4, "item_id": 2, "status": "cleared"},
    )
    assert pending.confirmation_token
    service.update_clearance_item_for_hr.assert_not_called()


def test_clearance_confirm_calls_domain_with_actor():
    service = MagicMock()
    actor = _actor()
    item = SimpleNamespace(
        id=2,
        item="Laptop",
        status=OffboardingClearanceStatus.CLEARED,
    )
    service.update_clearance_item_for_hr.return_value = item
    tool = UpdateOffboardingClearanceTool(service, get_user=lambda _id: actor)
    done = ToolExecutor(_registry(tool)).execute(
        _hr(),
        "update_offboarding_clearance",
        {"case_id": 4, "item_id": 2, "status": "cleared"},
        execute_writes=True,
    )
    assert done.data["status"] == "cleared"
    service.update_clearance_item_for_hr.assert_called_once()
    call = service.update_clearance_item_for_hr.call_args
    assert call.args[0] == 4
    assert call.args[1] == 2
    assert isinstance(call.args[2], OffboardingClearanceUpdateRequest)
    assert call.args[2].status == OffboardingClearanceStatus.CLEARED
    assert call.args[3] is actor


def test_task_mutation_requires_confirmation():
    service = MagicMock()
    tool = UpdateOffboardingTaskTool(service, get_user=lambda _id: _actor())
    pending = ToolExecutor(_registry(tool)).execute(
        _hr(),
        "update_offboarding_task",
        {"operation": "start", "task_id": 12, "case_id": 4},
    )
    assert pending.confirmation_token
    service.start_task_for_hr.assert_not_called()


def test_hr_task_start_complete_reopen():
    service = MagicMock()
    actor = _actor()
    task = SimpleNamespace(
        id=12, offboarding_case_id=4, status=OffboardingTaskStatus.IN_PROGRESS
    )
    service.start_task_for_hr.return_value = task
    service.complete_task_for_hr.return_value = SimpleNamespace(
        id=12, offboarding_case_id=4, status=OffboardingTaskStatus.COMPLETED
    )
    service.reopen_task_for_hr.return_value = SimpleNamespace(
        id=12, offboarding_case_id=4, status=OffboardingTaskStatus.PENDING
    )
    tool = UpdateOffboardingTaskTool(service, get_user=lambda _id: actor)
    executor = ToolExecutor(_registry(tool))
    executor.execute(
        _hr(),
        "update_offboarding_task",
        {"operation": "start", "task_id": 12, "case_id": 4},
        execute_writes=True,
    )
    service.start_task_for_hr.assert_called_once_with(4, 12)
    executor.execute(
        _hr(),
        "update_offboarding_task",
        {"operation": "complete", "task_id": 12, "case_id": 4},
        execute_writes=True,
    )
    service.complete_task_for_hr.assert_called_once()
    executor.execute(
        _hr(),
        "update_offboarding_task",
        {"operation": "reopen", "task_id": 12, "case_id": 4},
        execute_writes=True,
    )
    service.reopen_task_for_hr.assert_called_once_with(4, 12)


def test_employee_task_start_complete_uses_user_service():
    service = MagicMock()
    actor = MagicMock()
    actor.id = 9
    service.start_task_for_user.return_value = SimpleNamespace(
        id=12, offboarding_case_id=4, status=OffboardingTaskStatus.IN_PROGRESS
    )
    service.complete_task_for_user.return_value = SimpleNamespace(
        id=12, offboarding_case_id=4, status=OffboardingTaskStatus.COMPLETED
    )
    tool = UpdateOffboardingTaskTool(service, get_user=lambda _id: actor)
    executor = ToolExecutor(_registry(tool))
    executor.execute(
        _employee(),
        "update_offboarding_task",
        {"operation": "start", "task_id": 12},
        execute_writes=True,
    )
    service.start_task_for_user.assert_called_once_with(9, 12)
    executor.execute(
        _employee(),
        "update_offboarding_task",
        {"operation": "complete", "task_id": 12},
        execute_writes=True,
    )
    service.complete_task_for_user.assert_called_once()


def test_employee_cannot_reopen_task():
    service = MagicMock()
    tool = UpdateOffboardingTaskTool(service, get_user=lambda _id: _actor())
    with pytest.raises(ToolExecutionError, match="Not authorized"):
        ToolExecutor(_registry(tool)).execute(
            _employee(),
            "update_offboarding_task",
            {"operation": "reopen", "task_id": 12},
            execute_writes=True,
        )


def test_employee_task_domain_denial_preserved():
    service = MagicMock()
    service.start_task_for_user.side_effect = AppException(
        "Offboarding task not found", status_code=404
    )
    tool = UpdateOffboardingTaskTool(service, get_user=lambda _id: _actor())
    with pytest.raises(ToolExecutionError, match="not found"):
        ToolExecutor(_registry(tool)).execute(
            _employee(),
            "update_offboarding_task",
            {"operation": "start", "task_id": 999},
            execute_writes=True,
        )


def test_confirmation_wrong_user_rejected():
    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="complete_offboarding_case",
        arguments={"case_id": 4},
        summary="Complete case 4",
        target_type="offboarding_case",
        target_id=4,
    )
    with pytest.raises(ConfirmationError, match="does not belong"):
        verify_confirmation_token(token, user_id=9)


def test_confirmation_expired_rejected(monkeypatch):
    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="complete_offboarding_case",
        arguments={"case_id": 4},
        summary="Complete case 4",
        ttl_seconds=60,
    )
    import app.ai.confirmation.tokens as tokens_mod

    real_time = tokens_mod.time.time

    def future():
        return real_time() + 10_000

    monkeypatch.setattr(tokens_mod.time, "time", future)
    with pytest.raises(ConfirmationError, match="expired"):
        verify_confirmation_token(token, user_id=1)


def test_confirmation_body_tamper_rejected():
    token, _ = create_confirmation_token(
        user_id=1,
        tool_name="complete_offboarding_case",
        arguments={"case_id": 4},
        summary="Complete case 4",
    )
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    body, sig = raw.rsplit(b".", 1)
    payload = json.loads(body)
    payload["arguments"] = {"case_id": 999}
    tampered_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad = base64.urlsafe_b64encode(tampered_body + b"." + sig).decode("ascii").rstrip("=")
    with pytest.raises(ConfirmationError):
        verify_confirmation_token(bad, user_id=1)


def test_weaker_actor_cannot_confirm_hr_write():
    """Employee may hold a stolen token for an HR tool; re-authorize denies."""
    service = MagicMock()
    tool = CompleteOffboardingCaseTool(service)
    token, payload = create_confirmation_token(
        user_id=9,
        tool_name="complete_offboarding_case",
        arguments={"case_id": 4},
        summary="Complete case 4",
    )
    verified = verify_confirmation_token(token, user_id=9)
    assert verified.arguments == payload.arguments
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(_registry(tool)).execute(
            _employee(),
            verified.tool_name,
            verified.arguments,
            execute_writes=True,
        )
    service.complete.assert_not_called()


def test_replay_matches_shared_architecture_reexecutes_until_domain_fails():
    service = MagicMock()
    case = SimpleNamespace(
        id=4,
        employee_id=99,
        status=OffboardingStatus.COMPLETED,
        employee=SimpleNamespace(employment_status="inactive", user_id=None),
    )
    service.complete.side_effect = [
        case,
        AppException(
            "Cannot complete offboarding from status 'completed'", status_code=400
        ),
    ]
    tool = CompleteOffboardingCaseTool(service)
    executor = ToolExecutor(_registry(tool))
    args = {"case_id": 4}
    first = executor.execute(_hr(), "complete_offboarding_case", args, execute_writes=True)
    assert first.data["status"] == "completed"
    with pytest.raises(ToolExecutionError, match="Cannot complete"):
        executor.execute(_hr(), "complete_offboarding_case", args, execute_writes=True)


def test_agent_audit_phases(monkeypatch):
    audits: list[dict] = []

    def capture_audit(db, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(
        "app.ai.agents.offboarding.agent.record_ai_tool_audit",
        capture_audit,
    )
    service = MagicMock()
    case = SimpleNamespace(
        id=4,
        employee_id=99,
        status=OffboardingStatus.COMPLETED,
        employee=SimpleNamespace(employment_status="inactive", user_id=42),
    )
    service.complete.return_value = case
    agent = OffboardingAgent(
        llm_provider=MagicMock(),
        offboarding=service,
        employees=MagicMock(),
        get_user=lambda _id: _actor(),
        db=MagicMock(),
    )

    from app.ai.orchestration.tool_roundtrip import ToolRoundtripResult
    from app.ai.tools.schemas import ToolResult

    def fake_roundtrip(**kwargs):
        pending = ToolExecutor(agent.registry).execute(
            _hr(), "complete_offboarding_case", {"case_id": 4}
        )
        return ToolRoundtripResult(
            final_content="",
            model="m",
            tool_names_called=("complete_offboarding_case",),
            tool_results=(pending,),
            usage=None,
        )

    monkeypatch.setattr(
        "app.ai.agents.offboarding.agent.run_tool_roundtrip",
        fake_roundtrip,
    )
    from app.ai.agents.offboarding.schemas import OffboardingAgentRequest

    ask_result = agent.ask(
        OffboardingAgentRequest(question="Complete case 4", context=_hr())
    )
    assert ask_result.pending_confirmation is not None
    assert any(a["phase"] == "proposed" for a in audits)

    agent.confirm(token=ask_result.pending_confirmation.token, context=_hr())
    phases = [a["phase"] for a in audits]
    assert "confirmed" in phases
    assert "executed" in phases


def test_agent_audit_failed_on_bad_token(monkeypatch):
    audits: list[dict] = []

    def capture_audit(db, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(
        "app.ai.agents.offboarding.agent.record_ai_tool_audit",
        capture_audit,
    )
    agent = OffboardingAgent(
        llm_provider=MagicMock(),
        offboarding=MagicMock(),
        employees=MagicMock(),
        get_user=lambda _id: _actor(),
        db=MagicMock(),
    )
    from app.ai.agents.offboarding import OffboardingAgentValidationError

    with pytest.raises(OffboardingAgentValidationError):
        agent.confirm(token="not-a-valid-token", context=_hr())
    assert any(
        a["phase"] == "failed" and a.get("error_code") == "invalid_or_expired_token"
        for a in audits
    )


def test_write_module_no_repository_or_auth_service_imports():
    path = (
        Path(__file__).resolve().parents[2]
        / "ai"
        / "tools"
        / "offboarding_writes.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
    joined = " ".join(imported)
    assert "repository" not in joined.lower()
    assert "AuthService" not in joined
    assert "app.modules.identity.service" not in imported
    assert "app.modules.offboarding.repository" not in imported


def test_manager_and_candidate_denied_hr_writes():
    service = MagicMock()
    tool = CompleteOffboardingCaseTool(service)
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(tool, _manager(), CompleteOffboardingCaseInput(case_id=4))
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(tool, _candidate(), CompleteOffboardingCaseInput(case_id=4))
