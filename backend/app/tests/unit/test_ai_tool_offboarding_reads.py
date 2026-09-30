"""Unit tests for Offboarding Agent read tools."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools.authorization import authorize_tool
from app.ai.tools.exceptions import ToolAuthorizationError, ToolExecutionError
from app.ai.tools.offboarding_reads import (
    CaseScopedInput,
    FindEmployeesForOffboardingInput,
    FindEmployeesForOffboardingTool,
    GetExitInterviewTool,
    GetOffboardingCaseInput,
    GetOffboardingCaseTool,
    GetOffboardingClearanceTool,
    GetOffboardingProgressTool,
    GetOffboardingReadinessTool,
    ListOffboardingTasksInput,
    ListOffboardingTasksTool,
)
from app.modules.offboarding.models import (
    ExitInterviewStatus,
    OffboardingClearanceCategory,
    OffboardingClearanceStatus,
    OffboardingReason,
    OffboardingStatus,
    OffboardingTaskCategory,
    OffboardingTaskStatus,
)
from app.modules.offboarding.schemas import (
    OffboardingClearanceProgressResponse,
    OffboardingProgressResponse,
)


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"offboarding:read"}),
        employee_id=10,
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


def _case(**overrides):
    values = {
        "id": 4,
        "employee_id": 99,
        "employee": SimpleNamespace(
            id=99,
            full_name="Sam Staff",
            email="sam@test.com",
            position="Eng",
            employee_number="E1",
        ),
        "reason": OffboardingReason.RESIGNATION,
        "reason_details": "Personal",
        "last_working_day": date(2026, 10, 1),
        "status": OffboardingStatus.PENDING_CLEARANCE,
        "initiated_at": datetime(2026, 9, 1, tzinfo=UTC),
        "completed_at": None,
        "created_by": None,
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _progress():
    return OffboardingProgressResponse(
        offboarding_case_id=4,
        total_tasks=5,
        completed_tasks=3,
        skipped_tasks=0,
        pending_tasks=1,
        in_progress_tasks=1,
        required_total=4,
        required_completed=3,
        percentage=60,
        required_complete=False,
        overdue_tasks=0,
    )


def _clearance_progress():
    return OffboardingClearanceProgressResponse(
        offboarding_case_id=4,
        total=3,
        pending=1,
        cleared=2,
        not_applicable=0,
        percentage=66,
        clearance_complete=False,
    )


def test_hr_can_get_case_with_reason_details():
    service = MagicMock()
    case = _case()
    service.get_for_hr.return_value = case
    tool = GetOffboardingCaseTool(service)
    out = tool.execute(_hr(), GetOffboardingCaseInput(case_id=4)
    )
    assert out.case_id == 4
    assert out.reason_details == "Personal"
    assert out.employee_name == "Sam Staff"


def test_employee_case_hides_reason_details():
    service = MagicMock()
    case = _case()
    service.list_for_user.return_value = [case]
    tool = GetOffboardingCaseTool(service)
    out = tool.execute(_employee(), GetOffboardingCaseInput()
    )
    assert out.reason_details is None
    assert out.status == "pending_clearance"


def test_manager_without_offboarding_read_cannot_use_hr_lookup():
    service = MagicMock()
    tool = GetOffboardingCaseTool(service)
    with pytest.raises(ToolExecutionError, match="No offboarding case|No employee|Provide"):
        # Manager has employee_id so self path may run — without cases:
        service.list_for_user.return_value = []
        tool.execute(_manager(), GetOffboardingCaseInput(employee_id=99)
        )


def test_candidate_denied_self_tools():
    service = MagicMock()
    tool = GetOffboardingCaseTool(service)
    with pytest.raises(ToolExecutionError, match="No employee profile"):
        tool.execute(_candidate(), GetOffboardingCaseInput()
        )


def test_spoofed_foreign_case_rejected_for_employee():
    service = MagicMock()
    own = _case(id=4, employee_id=99)
    service.list_for_user.return_value = [own]
    tool = GetOffboardingCaseTool(service)
    with pytest.raises(ToolExecutionError, match="not found"):
        tool.execute(_employee(), GetOffboardingCaseInput(case_id=999)
        )


def test_readiness_terminal_completed_skips_can_complete():
    service = MagicMock()
    case = _case(status=OffboardingStatus.COMPLETED)
    service.get_for_hr.return_value = case
    tool = GetOffboardingReadinessTool(service)
    out = tool.execute(_hr(), CaseScopedInput(case_id=4)
    )
    assert out.ready is False
    assert out.terminal is True
    assert out.status == "completed"
    assert out.blockers == []
    service.can_complete.assert_not_called()


def test_readiness_terminal_cancelled():
    service = MagicMock()
    case = _case(status=OffboardingStatus.CANCELLED)
    service.get_for_hr.return_value = case
    tool = GetOffboardingReadinessTool(service)
    out = tool.execute(_hr(), CaseScopedInput(case_id=4)
    )
    assert out.terminal is True
    assert out.status == "cancelled"
    service.can_complete.assert_not_called()


def test_readiness_pending_calls_can_complete():
    service = MagicMock()
    case = _case(status=OffboardingStatus.PENDING_CLEARANCE)
    service.get_for_hr.return_value = case
    service.can_complete.return_value = (False, ["1 clearance item(s) remain pending"])
    tool = GetOffboardingReadinessTool(service)
    out = tool.execute(_hr(), CaseScopedInput(case_id=4)
    )
    assert out.ready is False
    assert out.terminal is False
    assert out.blockers == ["1 clearance item(s) remain pending"]
    service.can_complete.assert_called_once_with(4)


def test_progress_composes_service_numbers():
    service = MagicMock()
    case = _case()
    service.get_for_hr.return_value = case
    service.get_progress.return_value = _progress()
    service.get_clearance_progress.return_value = _clearance_progress()
    service.get_exit_interview_for_hr.return_value = None
    service.can_complete.return_value = (False, ["blocked"])
    tool = GetOffboardingProgressTool(service)
    out = tool.execute(_hr(), CaseScopedInput(case_id=4)
    )
    assert out.checklist.total_tasks == 5
    assert out.checklist.completed_tasks == 3
    assert out.clearance.pending == 1
    assert out.exit_interview.present is False
    assert out.ready_to_complete is False
    assert out.blockers == ["blocked"]


def test_exit_interview_hides_feedback_from_employee():
    service = MagicMock()
    case = _case()
    service.list_for_user.return_value = [case]
    interview = SimpleNamespace(
        id=1,
        offboarding_case_id=4,
        interviewer_employee_id=2,
        interviewer=SimpleNamespace(id=2, full_name="HR Person", email="hr@t.com"),
        scheduled_at=datetime(2026, 10, 1, 10, 0, tzinfo=UTC),
        ends_at=datetime(2026, 10, 1, 11, 0, tzinfo=UTC),
        meeting_url="https://meet.example/x",
        status=ExitInterviewStatus.COMPLETED,
        feedback="SECRET FEEDBACK",
        completed_at=datetime(2026, 10, 1, 11, 0, tzinfo=UTC),
        created_by_user_id=1,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        updated_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    service.get_exit_interview_for_hr.return_value = interview
    tool = GetExitInterviewTool(service)
    out = tool.execute(_employee(), CaseScopedInput()
    )
    assert out.feedback is None
    assert out.meeting_url == "https://meet.example/x"


def test_exit_interview_hr_sees_feedback():
    service = MagicMock()
    case = _case()
    service.get_for_hr.return_value = case
    interview = SimpleNamespace(
        id=1,
        offboarding_case_id=4,
        interviewer_employee_id=2,
        interviewer=SimpleNamespace(id=2, full_name="HR Person", email="hr@t.com"),
        scheduled_at=datetime(2026, 10, 1, 10, 0, tzinfo=UTC),
        ends_at=datetime(2026, 10, 1, 11, 0, tzinfo=UTC),
        meeting_url=None,
        status=ExitInterviewStatus.COMPLETED,
        feedback="Left well",
        completed_at=datetime(2026, 10, 1, 11, 0, tzinfo=UTC),
        created_by_user_id=1,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        updated_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    service.get_exit_interview_for_hr.return_value = interview
    tool = GetExitInterviewTool(service)
    out = tool.execute(_hr(), CaseScopedInput(case_id=4)
    )
    assert out.feedback == "Left well"


def test_tasks_employee_output_has_no_completed_by():
    service = MagicMock()
    case = _case()
    service.list_for_user.return_value = [case]
    task = SimpleNamespace(
        id=7,
        offboarding_case_id=4,
        title="Return laptop",
        description=None,
        category=OffboardingTaskCategory.EQUIPMENT,
        status=OffboardingTaskStatus.COMPLETED,
        is_required=True,
        assigned_to_employee_id=99,
        assigned_to=None,
        due_date=None,
        completed_at=datetime(2026, 9, 10, tzinfo=UTC),
        completed_by_user_id=9,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        updated_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    service.list_tasks_for_user.return_value = [task]
    tool = ListOffboardingTasksTool(service)
    out = tool.execute(_employee(), ListOffboardingTasksInput()
    )
    assert len(out.tasks) == 1
    assert not hasattr(out.tasks[0], "completed_by_user_id")
    dumped = out.tasks[0].model_dump()
    assert "completed_by_user_id" not in dumped


def test_find_employees_zero_one_many():
    employees = MagicMock()
    tool = FindEmployeesForOffboardingTool(employees)

    employees.list_employees.return_value = ([], 0)
    zero = tool.execute(_hr(), FindEmployeesForOffboardingInput(q="Nobody")
    )
    assert zero.count == 0
    assert zero.message is not None

    emp = SimpleNamespace(
        id=1,
        full_name="Sarah Smith",
        email="s@t.com",
        position="Eng",
        department=SimpleNamespace(name="IT"),
        employment_status=SimpleNamespace(value="active"),
    )
    employees.list_employees.return_value = ([emp], 1)
    one = tool.execute(_hr(), FindEmployeesForOffboardingInput(q="Sarah")
    )
    assert one.count == 1
    assert one.message is None

    emp2 = SimpleNamespace(
        id=2,
        full_name="Sarah Jones",
        email="sj@t.com",
        position="HR",
        department=None,
        employment_status=SimpleNamespace(value="active"),
    )
    employees.list_employees.return_value = ([emp, emp2], 2)
    many = tool.execute(_hr(), FindEmployeesForOffboardingInput(q="Sarah")
    )
    assert many.count == 2
    assert "do not pick" in (many.message or "").lower()


def test_find_employees_requires_hr_metadata():
    tool = FindEmployeesForOffboardingTool(MagicMock())
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(tool, _employee(), FindEmployeesForOffboardingInput(q="x"))
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(tool, _candidate(), FindEmployeesForOffboardingInput(q="x"))
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(tool, _manager(), FindEmployeesForOffboardingInput(q="x"))


def test_clearance_for_hr():
    service = MagicMock()
    case = _case()
    service.get_for_hr.return_value = case
    item = SimpleNamespace(
        id=1,
        category=OffboardingClearanceCategory.EQUIPMENT,
        item="Laptop",
        status=OffboardingClearanceStatus.PENDING,
        notes="check serial",
        completed_at=None,
    )
    service.list_clearance_for_hr.return_value = [item]
    service.get_clearance_progress.return_value = _clearance_progress()
    tool = GetOffboardingClearanceTool(service)
    out = tool.execute(_hr(), CaseScopedInput(case_id=4)
    )
    assert out.items[0].notes == "check serial"
    assert out.progress is not None
    assert out.progress.pending == 1


def test_no_storage_or_auth_fields_in_case_brief():
    service = MagicMock()
    case = _case()
    service.get_for_hr.return_value = case
    tool = GetOffboardingCaseTool(service)
    out = tool.execute(_hr(), GetOffboardingCaseInput(case_id=4)
    )
    keys = set(out.model_dump().keys())
    assert "storage_key" not in keys
    assert "is_active" not in keys
    assert "hashed_password" not in keys
