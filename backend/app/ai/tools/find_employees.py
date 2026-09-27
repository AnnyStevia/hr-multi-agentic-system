"""Read helper: find active employees by name for HR agent entity resolution."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.employees.service import EmployeeService
from app.shared.exceptions import AppException

_READ_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset({"recruitment:read"}),
    operates_on_current_user=False,
)


class FindEmployeesInput(BaseModel):
    model_config = {"extra": "forbid"}

    q: str = Field(min_length=1, max_length=120, description="Name search substring")
    limit: int = Field(default=20, ge=1, le=50)


class EmployeeMatch(BaseModel):
    model_config = {"extra": "forbid"}

    employee_id: int
    full_name: str
    email: str
    position: str | None = None
    department: str | None = None
    status: str


class FindEmployeesOutput(BaseModel):
    model_config = {"extra": "forbid"}

    query: str
    count: int
    employees: list[EmployeeMatch]
    message: str | None = None


class FindEmployeesTool(BaseTool):
    name = "find_employees"
    description = (
        "Search active employees by name substring for interviewer assignment. "
        "If count is 0 or greater than 1, ask the user to clarify with employee_id. "
        "Do not guess. Read-only."
    )
    metadata = _READ_META
    input_model = FindEmployeesInput
    output_model = FindEmployeesOutput

    def __init__(self, employee_service: EmployeeService):
        self._employees = employee_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, FindEmployeesInput)
        try:
            rows, _total = self._employees.list_employees(status="active", q=args.q.strip())
        except AppException as exc:
            raise ToolExecutionError(exc.message) from exc
        except Exception as exc:
            raise ToolExecutionError("Failed to search employees") from exc

        matches = [
            EmployeeMatch(
                employee_id=row.id,
                full_name=row.full_name,
                email=row.email,
                position=row.position,
                department=row.department.name if row.department else None,
                status=(
                    row.employment_status.value
                    if hasattr(row.employment_status, "value")
                    else str(row.employment_status)
                ),
            )
            for row in rows[: args.limit]
        ]
        message = None
        if len(matches) == 0:
            message = "No active employees matched. Ask for a different name or employee_id."
        elif len(matches) > 1:
            message = (
                "Multiple employees matched. Ask the user which employee_id to use; "
                "do not pick one automatically."
            )
        return FindEmployeesOutput(
            query=args.q.strip(),
            count=len(matches),
            employees=matches,
            message=message,
        )
