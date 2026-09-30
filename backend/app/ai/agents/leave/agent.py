"""Leave Agent — scoped reads + confirmation-gated LeaveService writes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.agents.leave.exceptions import LeaveAgentError, LeaveAgentValidationError
from app.ai.agents.leave.prompts import LEAVE_AGENT_SYSTEM_PROMPT
from app.ai.agents.leave.schemas import (
    LeaveAgentAnswer,
    LeaveAgentRequest,
    LeaveAgentUsage,
    PendingConfirmationInfo,
)
from app.ai.audit import record_ai_tool_audit
from app.ai.confirmation import (
    ConfirmationError,
    arguments_digest,
    verify_confirmation_token,
)
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm.base import LLMProvider
from app.ai.orchestration.tool_roundtrip import run_tool_roundtrip
from app.ai.tools.exceptions import (
    ToolAuthorizationError,
    ToolExecutionError,
    ToolValidationError,
)
from app.ai.tools.executor import ToolExecutor
from app.ai.tools.find_employees import FindEmployeesTool
from app.ai.tools.leave import (
    GetMyLeaveBalanceTool,
    GetMyLeaveRequestTool,
    GetMyWorkStatusTool,
    ListMyLeaveRequestsTool,
)
from app.ai.tools.leave_reads import (
    GetLeaveBalanceTool,
    GetLeavePolicyTool,
    GetLeaveRequestTool,
    ListCurrentlyOnLeaveTool,
    ListLeaveRequestsTool,
    ListLeaveTypesTool,
    ListPendingLeaveRequestsTool,
)
from app.ai.tools.leave_team_reads import (
    FindDirectReportsTool,
    GetDirectReportLeaveBalanceTool,
    GetTeamLeaveRequestTool,
    ListTeamCurrentlyOnLeaveTool,
    ListTeamLeaveRequestsTool,
    ListTeamPendingLeaveRequestsTool,
)
from app.ai.tools.leave_writes import (
    ApproveLeaveCancellationTool,
    ApproveLeaveRequestTool,
    CancelPendingLeaveRequestTool,
    CreateLeaveRequestTool,
    RejectLeaveCancellationTool,
    RejectLeaveRequestTool,
    RequestLeaveCancellationTool,
)
from app.ai.tools.registry import ToolRegistry
from app.modules.employees.service import EmployeeService
from app.modules.leave.service import LeaveService

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_MAX_TOOL_CALLS = 8
DEFAULT_MAX_TOOL_ROUNDS = 3


class LeaveAgent:
    """Leave assistant with scoped reads and confirmation-gated writes."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        leave_service: LeaveService,
        employee_service: EmployeeService,
        db: Session | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
        max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    ) -> None:
        self._llm = llm_provider
        self._max_output_tokens = max_output_tokens
        self._max_tool_calls = max_tool_calls
        self._max_tool_rounds = max_tool_rounds
        self._db = db
        self._registry = ToolRegistry()
        # Self reads
        self._registry.register(GetMyLeaveBalanceTool(leave_service))
        self._registry.register(ListMyLeaveRequestsTool(leave_service))
        self._registry.register(GetMyLeaveRequestTool(leave_service))
        self._registry.register(GetMyWorkStatusTool(leave_service))
        # Manager / team reads
        self._registry.register(FindDirectReportsTool(leave_service))
        self._registry.register(GetDirectReportLeaveBalanceTool(leave_service))
        self._registry.register(ListTeamLeaveRequestsTool(leave_service))
        self._registry.register(ListTeamPendingLeaveRequestsTool(leave_service))
        self._registry.register(GetTeamLeaveRequestTool(leave_service))
        self._registry.register(ListTeamCurrentlyOnLeaveTool(leave_service))
        # HR reads
        self._registry.register(FindEmployeesTool(employee_service))
        self._registry.register(ListLeaveTypesTool(leave_service))
        self._registry.register(GetLeaveBalanceTool(leave_service))
        self._registry.register(GetLeaveRequestTool(leave_service))
        self._registry.register(ListLeaveRequestsTool(leave_service))
        self._registry.register(ListPendingLeaveRequestsTool(leave_service))
        self._registry.register(ListCurrentlyOnLeaveTool(leave_service))
        self._registry.register(GetLeavePolicyTool(leave_service))
        # Writes (confirmation-gated)
        self._registry.register(CreateLeaveRequestTool(leave_service))
        self._registry.register(ApproveLeaveRequestTool(leave_service))
        self._registry.register(RejectLeaveRequestTool(leave_service))
        self._registry.register(CancelPendingLeaveRequestTool(leave_service))
        self._registry.register(RequestLeaveCancellationTool(leave_service))
        self._registry.register(ApproveLeaveCancellationTool(leave_service))
        self._registry.register(RejectLeaveCancellationTool(leave_service))

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def ask(self, request: LeaveAgentRequest) -> LeaveAgentAnswer:
        question = (request.question or "").strip()
        if not question:
            raise LeaveAgentValidationError("Question must not be empty")

        try:
            result = run_tool_roundtrip(
                provider=self._llm,
                context=request.context,
                registry=self._registry,
                user_prompt=question,
                system_prompt=LEAVE_AGENT_SYSTEM_PROMPT,
                tool_choice="auto",
                max_tokens=self._max_output_tokens,
                max_tool_calls=self._max_tool_calls,
                max_tool_rounds=self._max_tool_rounds,
            )
        except ToolAuthorizationError as exc:
            raise LeaveAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            raise LeaveAgentValidationError(str(exc)) from exc
        except ToolExecutionError as exc:
            raise LeaveAgentError(str(exc)) from exc
        except LLMConfigurationError as exc:
            raise LeaveAgentError("Leave agent is not configured") from exc
        except LLMProviderError as exc:
            raise LeaveAgentError("Leave agent failed") from exc

        pending = None
        for tool_result in result.tool_results:
            if tool_result.confirmation_token:
                pending = PendingConfirmationInfo(
                    token=tool_result.confirmation_token,
                    tool_name=tool_result.tool_name,
                    summary=tool_result.confirmation_summary
                    or "Please confirm this write action.",
                    expires_at=tool_result.confirmation_expires_at or 0,
                )
                self._audit(
                    actor_user_id=request.context.user_id,
                    tool_name=tool_result.tool_name,
                    phase="proposed",
                    arguments=(tool_result.data or {}).get("arguments") or {},
                    success=True,
                )
                break

        answer = (result.final_content or "").strip()
        if not answer:
            if pending:
                answer = (
                    "I prepared a write action that requires your confirmation. "
                    "Use the Confirm button below to proceed — nothing has been changed yet."
                )
            elif any(not tr.success for tr in result.tool_results):
                answer = (
                    "I couldn't retrieve that leave information with the available tools. "
                    "Employees can only see their own leave; looking up someone else's "
                    "balance requires HR/Admin access. Try 'What's my leave balance?' "
                    "or ask as HR with the employee's name."
                )
            else:
                answer = "I don't have enough information to answer that."

        usage = None
        if result.usage is not None:
            usage = LeaveAgentUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                thinking_tokens=result.usage.thinking_tokens,
                total_tokens=result.usage.total_tokens,
            )

        return LeaveAgentAnswer(
            answer=answer,
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=usage,
            pending_confirmation=pending,
        )

    def confirm(self, *, token: str, context) -> LeaveAgentAnswer:
        try:
            payload = verify_confirmation_token(token, user_id=context.user_id)
        except ConfirmationError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name="unknown",
                phase="failed",
                arguments={},
                success=False,
                error_code="invalid_or_expired_token",
            )
            raise LeaveAgentValidationError(exc.message) from exc

        self._audit(
            actor_user_id=context.user_id,
            tool_name=payload.tool_name,
            phase="confirmed",
            arguments=payload.arguments,
            target_type=payload.target_type,
            target_id=payload.target_id,
            success=True,
        )

        executor = ToolExecutor(self._registry)
        try:
            result = executor.execute(
                context,
                payload.tool_name,
                payload.arguments,
                execute_writes=True,
            )
        except ToolAuthorizationError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                target_type=payload.target_type,
                target_id=payload.target_id,
                success=False,
                error_code="unauthorized",
            )
            raise LeaveAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                success=False,
                error_code="validation",
            )
            raise LeaveAgentValidationError(str(exc)) from exc
        except ToolExecutionError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                target_type=payload.target_type,
                target_id=payload.target_id,
                success=False,
                error_code="execution",
            )
            # Surface LeaveService business messages (balance, policy, overlap) to the client.
            raise LeaveAgentValidationError(str(exc)) from exc

        self._audit(
            actor_user_id=context.user_id,
            tool_name=payload.tool_name,
            phase="executed",
            arguments=payload.arguments,
            target_type=payload.target_type,
            target_id=payload.target_id,
            success=True,
        )

        summary = payload.summary
        data = result.data or {}
        answer = _format_confirm_answer(payload.tool_name, summary, data)
        return LeaveAgentAnswer(
            answer=answer,
            model="confirmed-action",
            tool_names_called=[payload.tool_name],
            usage=None,
            pending_confirmation=None,
        )

    def _audit(
        self,
        *,
        actor_user_id: int,
        tool_name: str,
        phase: str,
        arguments: dict,
        target_type: str | None = None,
        target_id: int | None = None,
        success: bool = True,
        error_code: str | None = None,
    ) -> None:
        if self._db is None:
            return
        try:
            if target_type is None and "request_id" in arguments:
                target_type, target_id = "leave_request", int(arguments["request_id"])
            record_ai_tool_audit(
                self._db,
                actor_user_id=actor_user_id,
                tool_name=tool_name,
                phase=phase,
                target_type=target_type,
                target_id=target_id,
                arguments_digest=arguments_digest(arguments) if arguments else None,
                success=success,
                error_code=error_code,
            )
        except Exception:
            # Audit must not break the agent path.
            pass


def _format_confirm_answer(tool_name: str, summary: str, data: dict) -> str:
    """Human-readable confirm result without dumping raw tool JSON."""
    lines = [
        f"Confirmed and completed: {tool_name}.",
        "",
        summary.strip() or "Action completed.",
    ]
    facts: list[str] = []
    for key in (
        "request_id",
        "employee_id",
        "leave_type_id",
        "leave_type_name",
        "start_date",
        "end_date",
        "requested_days",
        "status",
        "cancellation_status",
        "manager_approval",
        "hr_approval",
    ):
        if key in data and data[key] is not None and data[key] != "":
            facts.append(f"- {key}: {data[key]}")
    if facts:
        lines.append("")
        lines.append("Result:")
        lines.extend(facts)
    return "\n".join(lines)
