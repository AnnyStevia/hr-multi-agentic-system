"""HTTP API for the Leave Agent (read-only, HR staff)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.ai.agents.leave import (
    LeaveAgent,
    LeaveAgentError,
    LeaveAgentRequest,
    LeaveAgentValidationError,
)
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.modules.employees.dependencies import get_employee_service
from app.modules.employees.service import EmployeeService
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.leave.dependencies import get_leave_service
from app.modules.leave.service import LeaveService

router = APIRouter(prefix="/ai/leave", tags=["AI Leave"])


class LeaveAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)


class LeaveUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class LeaveAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: LeaveUsageResponse | None = None


def get_leave_agent(
    leave_service: LeaveService = Depends(get_leave_service),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> LeaveAgent:
    return LeaveAgent(
        llm_provider=get_llm_provider(),
        leave_service=leave_service,
        employee_service=employee_service,
    )


def _to_response(result) -> LeaveAskResponse:
    usage = None
    if result.usage is not None:
        usage = LeaveUsageResponse(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            thinking_tokens=result.usage.thinking_tokens,
            total_tokens=result.usage.total_tokens,
        )
    return LeaveAskResponse(
        answer=result.answer,
        model=result.model,
        tool_names_called=result.tool_names_called,
        usage=usage,
    )


@router.post("/ask", response_model=LeaveAskResponse)
def ask_leave(
    payload: LeaveAskRequest,
    _: User = Depends(require_hr_staff("leaves:read")),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: LeaveAgent = Depends(get_leave_agent),
) -> LeaveAskResponse:
    try:
        result = agent.ask(
            LeaveAgentRequest(question=payload.question, context=context)
        )
    except LeaveAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except LeaveAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the leave question right now.",
        ) from exc
    return _to_response(result)
