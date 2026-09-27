"""Recruitment Agent — HR Q&A via authorized recruitment + interview tools."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.ai.agents.recruitment.exceptions import (
    RecruitmentAgentError,
    RecruitmentAgentValidationError,
)
from app.ai.agents.recruitment.prompts import RECRUITMENT_AGENT_SYSTEM_PROMPT
from app.ai.agents.recruitment.schemas import (
    PendingConfirmationInfo,
    RecruitmentAgentAnswer,
    RecruitmentAgentRequest,
    RecruitmentAgentUsage,
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
from app.ai.tools.interview_reads import (
    GetCandidateInterviewsTool,
    GetInterviewFeedbackTool,
    GetInterviewTool,
    GetUpcomingInterviewsTool,
    ListInterviewsTool,
)
from app.ai.tools.interview_writes import (
    CreateInterviewInvitationTool,
    RecordInterviewOutcomeTool,
    RetryInterviewMeetingTool,
)
from app.ai.tools.recruitment import (
    GetApplicationFitTool,
    GetApplicationTool,
    GetJobTool,
    ListJobApplicationsTool,
    ListRecruitmentApplicationsTool,
    RejectApplicationTool,
    ShortlistApplicationTool,
)
from app.ai.tools.registry import ToolRegistry
from app.modules.employees.service import EmployeeService
from app.modules.identity.models import User
from app.modules.interviews.meeting_service import InterviewMeetingService
from app.modules.interviews.service import InterviewService
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.service import JobService

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_MAX_TOOL_CALLS = 6


class RecruitmentAgent:
    """HR recruitment assistant using ToolExecutor-authorized read/write tools."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        job_service: JobService,
        application_service: ApplicationService,
        interview_service: InterviewService,
        meeting_service: InterviewMeetingService,
        employee_service: EmployeeService,
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
        self._registry.register(GetJobTool(job_service))
        self._registry.register(GetApplicationTool(application_service))
        self._registry.register(GetApplicationFitTool(application_service))
        self._registry.register(ListJobApplicationsTool(application_service))
        self._registry.register(ListRecruitmentApplicationsTool(application_service))
        self._registry.register(ShortlistApplicationTool(application_service))
        self._registry.register(RejectApplicationTool(application_service))
        self._registry.register(GetInterviewTool(interview_service))
        self._registry.register(ListInterviewsTool(interview_service))
        self._registry.register(GetInterviewFeedbackTool(interview_service))
        self._registry.register(GetCandidateInterviewsTool(interview_service))
        self._registry.register(GetUpcomingInterviewsTool(interview_service))
        self._registry.register(FindEmployeesTool(employee_service))
        self._registry.register(
            CreateInterviewInvitationTool(interview_service, get_user)
        )
        self._registry.register(RetryInterviewMeetingTool(meeting_service))
        self._registry.register(RecordInterviewOutcomeTool(interview_service))

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def ask(self, request: RecruitmentAgentRequest) -> RecruitmentAgentAnswer:
        question = (request.question or "").strip()
        if not question:
            raise RecruitmentAgentValidationError("Question must not be empty")

        try:
            result = run_tool_roundtrip(
                provider=self._llm,
                context=request.context,
                registry=self._registry,
                user_prompt=question,
                system_prompt=RECRUITMENT_AGENT_SYSTEM_PROMPT,
                tool_choice="auto",
                max_tokens=self._max_output_tokens,
                max_tool_calls=self._max_tool_calls,
            )
        except ToolAuthorizationError as exc:
            raise RecruitmentAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            raise RecruitmentAgentValidationError(str(exc)) from exc
        except ToolExecutionError as exc:
            raise RecruitmentAgentError(str(exc)) from exc
        except LLMConfigurationError as exc:
            raise RecruitmentAgentError("Recruitment agent is not configured") from exc
        except LLMProviderError as exc:
            raise RecruitmentAgentError("Recruitment agent failed") from exc

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
                    "Review the details and confirm to proceed — nothing has been changed yet."
                )
            else:
                answer = "I don't have enough information to answer that."

        usage = None
        if result.usage is not None:
            usage = RecruitmentAgentUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                thinking_tokens=result.usage.thinking_tokens,
                total_tokens=result.usage.total_tokens,
            )

        return RecruitmentAgentAnswer(
            answer=answer,
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=usage,
            pending_confirmation=pending,
        )

    def confirm(self, *, token: str, context) -> RecruitmentAgentAnswer:
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
            raise RecruitmentAgentValidationError(exc.message) from exc

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
            raise RecruitmentAgentError(str(exc)) from exc
        except ToolValidationError as exc:
            self._audit(
                actor_user_id=context.user_id,
                tool_name=payload.tool_name,
                phase="failed",
                arguments=payload.arguments,
                success=False,
                error_code="validation",
            )
            raise RecruitmentAgentValidationError(str(exc)) from exc
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
            raise RecruitmentAgentError(str(exc)) from exc

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
        answer = (
            f"Confirmed and completed: {payload.tool_name}.\n\n"
            f"{summary}\n\n"
            f"Result: {data}"
        )
        return RecruitmentAgentAnswer(
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
            if target_type is None and "interview_id" in arguments:
                target_type, target_id = "interview", int(arguments["interview_id"])
            elif target_type is None and "application_id" in arguments:
                target_type, target_id = "application", int(arguments["application_id"])
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
