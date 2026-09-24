"""AI tools that wrap Core HR leave services (no direct DB access)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.leave.schemas import LeaveBalanceResponse
from app.modules.leave.service import LeaveService
from app.shared.exceptions import AppException


class GetMyLeaveBalanceInput(BaseModel):
    """No arguments — employee identity comes only from AIExecutionContext."""

    model_config = {"extra": "forbid"}


class LeaveBalanceItem(BaseModel):
    model_config = {"extra": "forbid"}

    leave_type_id: int
    leave_type_name: str
    days_allowed: int
    days_used: int
    days_pending: int
    days_available: int


class GetMyLeaveBalanceOutput(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    year: int
    balances: list[LeaveBalanceItem] = Field(default_factory=list)


class GetMyLeaveBalanceTool(BaseTool):
    """Read-only leave balances for the authenticated employee via LeaveService."""

    name = "get_my_leave_balance"
    description = (
        "Return the authenticated employee's leave balances for the current year "
        "(days allowed, used, pending, and available per leave type). "
        "Does not accept employee_id or other identity arguments."
    )
    metadata = ToolMetadata(
        operation="read",
        required_permissions=frozenset({"leaves:read"}),
        operates_on_current_user=True,
    )
    input_model = GetMyLeaveBalanceInput
    output_model = GetMyLeaveBalanceOutput

    def __init__(self, leave_service: LeaveService):
        self._leave_service = leave_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetMyLeaveBalanceInput)
        if context.employee_id is None:
            raise ToolExecutionError(
                "No employee profile for the authenticated user"
            )

        try:
            rows = self._leave_service.get_balances(context.employee_id)
        except AppException as exc:
            raise ToolExecutionError(exc.message) from exc
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                "Failed to retrieve leave balances"
            ) from exc

        return _to_output(context.employee_id, rows)


def _to_output(
    employee_id: int,
    rows: list[LeaveBalanceResponse],
) -> GetMyLeaveBalanceOutput:
    year = rows[0].year if rows else datetime.now(UTC).year
    balances = [
        LeaveBalanceItem(
            leave_type_id=row.leave_type_id,
            leave_type_name=row.leave_type_name,
            days_allowed=row.days_allowed,
            days_used=row.days_used,
            days_pending=row.days_pending,
            days_available=row.days_available,
        )
        for row in rows
    ]
    return GetMyLeaveBalanceOutput(
        employee_id=employee_id,
        year=year,
        balances=balances,
    )
