"""Offboarding Agent — reads + confirmation-gated OffboardingService writes."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.ai.agents.offboarding.exceptions import (
    OffboardingAgentAuthorizationError,
    OffboardingAgentError,
    OffboardingAgentValidationError,
)
from app.ai.agents.offboarding.prompts import OFFBOARDING_AGENT_SYSTEM_PROMPT
from app.ai.agents.offboarding.schemas import (
    OFFBOARDING_AGENT_ID,
    OffboardingAgentAnswer,
    OffboardingAgentRequest,
    OffboardingAgentUsage,
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
    ToolNotFoundError,
    ToolValidationError,
)
from app.ai.tools.executor import ToolExecutor
from app.ai.tools.offboarding_reads import (
    FindEmployeesForOffboardingTool,
    GetExitInterviewTool,
    GetOffboardingCaseTool,
    GetOffboardingClearanceTool,
    GetOffboardingProgressTool,
    GetOffboardingReadinessTool,
    ListOffboardingTasksTool,
)
from app.ai.tools.offboarding_writes import (
    CompleteOffboardingCaseTool,
    UpdateOffboardingClearanceTool,
    UpdateOffboardingTaskTool,
)
from app.ai.tools.registry import ToolRegistry
from app.modules.employees.service import EmployeeService
from app.modules.identity.models import User
from app.modules.offboarding.service import OffboardingService

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_MAX_TOOL_CALLS = 8

_AUTH_TOKENS = (
    "not authorized",
    "unauthorized",
    "permission",
    "forbidden",
    "access denied",
    "not allowed",
)

_VALIDATION_TOKENS = (
    "not found",
    "must not be empty",
    "must be",
    "provide case_id",
    "invalid",
    "empty",
    "cannot be completed",
    "cannot start",
    "cannot complete",
    "cannot reopen",
)


class OffboardingAgent:
    """Offboarding assistant with reads and confirmation-gated writes."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        offboarding: OffboardingService,
        employees: EmployeeService,
        get_user: Callable[[int], User | None],
        db: Session | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    ) -> None:
        self._llm = llm_provider
        self._max_output_tokens = max_output_tokens
        self._max_tool_calls = max_tool_calls
        self._db = db
        self._registry = ToolRegistry()
        # Reads
        self._registry.register(FindEmployeesForOffboardingTool(employees))
        self._registry.register(GetOffboardingCaseTool(offboarding))
        self._registry.register(GetOffboardingProgressTool(offboarding))
        self._registry.register(ListOffboardingTasksTool(offboarding))
        self._registry.register(GetOffboardingClearanceTool(offboarding))
        self._registry.register(GetExitInterviewTool(offboarding))
        self._registry.register(GetOffboardingReadinessTool(offboarding))
        # Writes (confirmation-gated)
        self._registry.register(CompleteOffboardingCaseTool(offboarding))
        self._registry.register(UpdateOffboardingClearanceTool(offboarding, get_user))
        self._registry.register(UpdateOffboardingTaskTool(offboarding, get_user))

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def agent_id(self) -> str:
        return OFFBOARDING_AGENT_ID

    def ask(self, request: OffboardingAgentRequest) -> OffboardingAgentAnswer:
        question = (request.question or "").strip()
        if not question:
            raise OffboardingAgentValidationError("Question must not be empty")

        try:
            result = run_tool_roundtrip(
                provider=self._llm,
                context=request.context,
                registry=self._registry,
                user_prompt=question,
                system_prompt=OFFBOARDING_AGENT_SYSTEM_PROMPT,
                tool_choice="auto",
                max_tokens=self._max_output_tokens,
                max_tool_calls=self._max_tool_calls,
            )
        except ToolAuthorizationError as exc:
            raise OffboardingAgentAuthorizationError(str(exc)) from exc
        except ToolValidationError as exc:
            raise OffboardingAgentValidationError(str(exc)) from exc
        except ToolExecutionError as exc:
            self._raise_from_tool_message(str(exc))
        except LLMConfigurationError as exc:
            raise OffboardingAgentError("Offboarding agent is not configured") from exc
        except LLMProviderError as exc:
            raise OffboardingAgentError("Offboarding agent failed") from exc

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
            else:
                answer = "I don't have enough information to answer that."

        usage = None
        if result.usage is not None:
            usage = OffboardingAgentUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                thinking_tokens=result.usage.thinking_tokens,
                total_tokens=result.usage.total_tokens,
            )

        return OffboardingAgentAnswer(
            answer=answer,
            agent_id=OFFBOARDING_AGENT_ID,
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=usage,
            pending_confirmation=pending,
        )

    def confirm(self, *, token: str, context) -> OffboardingAgentAnswer:
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
            raise OffboardingAgentValidationError(exc.message) from exc

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
        except ToolNotFoundError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                target_type=payload.target_type,
                target_id=payload.target_id,
                success=False,
                error_code="unknown_tool",
            )
            raise OffboardingAgentValidationError(str(exc)) from exc
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
            raise OffboardingAgentAuthorizationError(str(exc)) from exc
        except ToolValidationError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                success=False,
                error_code="validation",
            )
            raise OffboardingAgentValidationError(str(exc)) from exc
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
            raise OffboardingAgentValidationError(str(exc)) from exc

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
        return OffboardingAgentAnswer(
            answer=answer,
            agent_id=OFFBOARDING_AGENT_ID,
            model="confirmed-action",
            tool_names_called=[payload.tool_name],
            usage=None,
            pending_confirmation=None,
        )

    def tool_names(self) -> list[str]:
        return [tool.name for tool in self._registry.list_tools()]

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
            if target_type is None and "item_id" in arguments:
                target_type, target_id = (
                    "offboarding_clearance_item",
                    int(arguments["item_id"]),
                )
            elif target_type is None and "task_id" in arguments:
                target_type, target_id = "offboarding_task", int(arguments["task_id"])
            elif target_type is None and "case_id" in arguments:
                target_type, target_id = "offboarding_case", int(arguments["case_id"])
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
            pass

    def _raise_from_tool_message(self, message: str) -> None:
        lower = message.lower()
        if any(token in lower for token in _AUTH_TOKENS):
            raise OffboardingAgentAuthorizationError(message)
        if any(token in lower for token in _VALIDATION_TOKENS):
            raise OffboardingAgentValidationError(message)
        raise OffboardingAgentError(message)


def _format_confirm_answer(tool_name: str, summary: str, data: dict) -> str:
    lines = [
        f"Confirmed and completed: {tool_name}.",
        "",
        summary.strip() or "Action completed.",
    ]
    facts: list[str] = []
    for key in (
        "action",
        "operation",
        "case_id",
        "employee_id",
        "item_id",
        "task_id",
        "item",
        "status",
        "employment_status",
        "account_deactivated",
        "message",
    ):
        if key in data and data[key] is not None and data[key] != "":
            facts.append(f"- {key}: {data[key]}")
    if facts:
        lines.append("")
        lines.append("Result:")
        lines.extend(facts)
    return "\n".join(lines)
