"""Onboarding Agent — scoped reads + confirmation-gated OnboardingService writes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.agents.onboarding.exceptions import (
    OnboardingAgentError,
    OnboardingAgentValidationError,
)
from app.ai.agents.onboarding.prompts import ONBOARDING_AGENT_SYSTEM_PROMPT
from app.ai.agents.onboarding.schemas import (
    OnboardingAgentAnswer,
    OnboardingAgentRequest,
    OnboardingAgentUsage,
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
from app.ai.tools.find_employees import FindEmployeesTool
from app.ai.tools.onboarding_reads import (
    GetMyOnboardingProgressTool,
    GetMyOnboardingTool,
    GetOnboardingByEmployeeTool,
    GetOnboardingProgressTool,
    GetOnboardingTool,
    ListMyOnboardingTasksTool,
    ListOnboardingTasksTool,
    ListOnboardingTemplatesTool,
    ListOnboardingsTool,
)
from app.ai.tools.onboarding_writes import (
    AcknowledgeOnboardingTaskTool,
    CompleteManualOnboardingTaskTool,
    CompleteOnboardingTool,
)
from app.ai.tools.registry import ToolRegistry
from app.modules.employees.service import EmployeeService
from app.modules.onboarding.service import OnboardingService

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_MAX_TOOL_CALLS = 8


class OnboardingAgent:
    """Onboarding assistant with scoped reads and confirmation-gated writes."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        onboarding_service: OnboardingService,
        employee_service: EmployeeService,
        db: Session | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    ) -> None:
        self._llm = llm_provider
        self._max_output_tokens = max_output_tokens
        self._max_tool_calls = max_tool_calls
        self._db = db
        self._registry = ToolRegistry()
        # Self reads
        self._registry.register(GetMyOnboardingTool(onboarding_service))
        self._registry.register(GetMyOnboardingProgressTool(onboarding_service))
        self._registry.register(ListMyOnboardingTasksTool(onboarding_service))
        # HR reads
        self._registry.register(FindEmployeesTool(employee_service))
        self._registry.register(ListOnboardingsTool(onboarding_service))
        self._registry.register(GetOnboardingTool(onboarding_service))
        self._registry.register(GetOnboardingByEmployeeTool(onboarding_service))
        self._registry.register(GetOnboardingProgressTool(onboarding_service))
        self._registry.register(ListOnboardingTasksTool(onboarding_service))
        self._registry.register(ListOnboardingTemplatesTool(onboarding_service))
        # Writes (confirmation-gated)
        self._registry.register(AcknowledgeOnboardingTaskTool(onboarding_service))
        self._registry.register(CompleteManualOnboardingTaskTool(onboarding_service))
        self._registry.register(CompleteOnboardingTool(onboarding_service))

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def ask(self, request: OnboardingAgentRequest) -> OnboardingAgentAnswer:
        question = (request.question or "").strip()
        if not question:
            raise OnboardingAgentValidationError("Question must not be empty")

        try:
            result = run_tool_roundtrip(
                provider=self._llm,
                context=request.context,
                registry=self._registry,
                user_prompt=question,
                system_prompt=ONBOARDING_AGENT_SYSTEM_PROMPT,
                tool_choice="auto",
                max_tokens=self._max_output_tokens,
                max_tool_calls=self._max_tool_calls,
            )
        except ToolAuthorizationError as exc:
            raise OnboardingAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            raise OnboardingAgentValidationError(str(exc)) from exc
        except ToolExecutionError as exc:
            raise OnboardingAgentError(str(exc)) from exc
        except LLMConfigurationError as exc:
            raise OnboardingAgentError("Onboarding agent is not configured") from exc
        except LLMProviderError as exc:
            raise OnboardingAgentError("Onboarding agent failed") from exc

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
            usage = OnboardingAgentUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                thinking_tokens=result.usage.thinking_tokens,
                total_tokens=result.usage.total_tokens,
            )

        return OnboardingAgentAnswer(
            answer=answer,
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=usage,
            pending_confirmation=pending,
        )

    def confirm(self, *, token: str, context) -> OnboardingAgentAnswer:
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
            raise OnboardingAgentValidationError(exc.message) from exc

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
            raise OnboardingAgentValidationError(str(exc)) from exc
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
            raise OnboardingAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                success=False,
                error_code="validation",
            )
            raise OnboardingAgentValidationError(str(exc)) from exc
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
            raise OnboardingAgentValidationError(str(exc)) from exc

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
        return OnboardingAgentAnswer(
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
            if target_type is None and "task_id" in arguments:
                target_type, target_id = "onboarding_task", int(arguments["task_id"])
            elif target_type is None and "onboarding_id" in arguments:
                target_type, target_id = "onboarding", int(arguments["onboarding_id"])
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
        "action",
        "task_id",
        "onboarding_id",
        "employee_id",
        "status",
        "message",
    ):
        if key in data and data[key] is not None and data[key] != "":
            facts.append(f"- {key}: {data[key]}")
    if facts:
        lines.append("")
        lines.append("Result:")
        lines.extend(facts)
    return "\n".join(lines)
