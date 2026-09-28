"""Training Agent — scoped reads + confirmation-gated TrainingService writes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.agents.training.exceptions import (
    TrainingAgentError,
    TrainingAgentValidationError,
)
from app.ai.agents.training.prompts import TRAINING_AGENT_SYSTEM_PROMPT
from app.ai.agents.training.schemas import (
    PendingConfirmationInfo,
    TrainingAgentAnswer,
    TrainingAgentRequest,
    TrainingAgentUsage,
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
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.training_reads import (
    ListMyTrainingAssignmentsTool,
    ListOnboardingTrainingAssignmentsTool,
    ListTrainingsTool,
)
from app.ai.tools.training_writes import (
    AssignTrainingToOnboardingTool,
    CompleteMyTrainingAssignmentTool,
)
from app.modules.training.service import TrainingService

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_MAX_TOOL_CALLS = 8


class TrainingAgent:
    """Training assistant with scoped reads and confirmation-gated writes."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        training_service: TrainingService,
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
        self._registry.register(ListMyTrainingAssignmentsTool(training_service))
        self._registry.register(ListTrainingsTool(training_service))
        self._registry.register(ListOnboardingTrainingAssignmentsTool(training_service))
        # Writes (confirmation-gated)
        self._registry.register(CompleteMyTrainingAssignmentTool(training_service))
        self._registry.register(AssignTrainingToOnboardingTool(training_service))

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def ask(self, request: TrainingAgentRequest) -> TrainingAgentAnswer:
        question = (request.question or "").strip()
        if not question:
            raise TrainingAgentValidationError("Question must not be empty")

        try:
            result = run_tool_roundtrip(
                provider=self._llm,
                context=request.context,
                registry=self._registry,
                user_prompt=question,
                system_prompt=TRAINING_AGENT_SYSTEM_PROMPT,
                tool_choice="auto",
                max_tokens=self._max_output_tokens,
                max_tool_calls=self._max_tool_calls,
            )
        except ToolAuthorizationError as exc:
            raise TrainingAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            raise TrainingAgentValidationError(str(exc)) from exc
        except ToolExecutionError as exc:
            raise TrainingAgentError(str(exc)) from exc
        except LLMConfigurationError as exc:
            raise TrainingAgentError("Training agent is not configured") from exc
        except LLMProviderError as exc:
            raise TrainingAgentError("Training agent failed") from exc

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
            usage = TrainingAgentUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                thinking_tokens=result.usage.thinking_tokens,
                total_tokens=result.usage.total_tokens,
            )

        return TrainingAgentAnswer(
            answer=answer,
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=usage,
            pending_confirmation=pending,
        )

    def confirm(self, *, token: str, context) -> TrainingAgentAnswer:
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
            raise TrainingAgentValidationError(exc.message) from exc

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
            raise TrainingAgentValidationError(str(exc)) from exc
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
            raise TrainingAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                success=False,
                error_code="validation",
            )
            raise TrainingAgentValidationError(str(exc)) from exc
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
            raise TrainingAgentValidationError(str(exc)) from exc

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
        return TrainingAgentAnswer(
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
            if target_type is None and "training_assignment_id" in arguments:
                target_type, target_id = (
                    "onboarding_training",
                    int(arguments["training_assignment_id"]),
                )
            elif target_type is None and "onboarding_id" in arguments:
                target_type, target_id = "onboarding", int(arguments["onboarding_id"])
            elif target_type is None and "training_id" in arguments:
                target_type, target_id = "training", int(arguments["training_id"])
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
        "training_assignment_id",
        "assignment_id",
        "onboarding_id",
        "training_id",
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
