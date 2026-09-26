"""Recruitment Agent — HR Q&A via authorized recruitment + interview tools."""

from __future__ import annotations

from app.ai.agents.recruitment.exceptions import (
    RecruitmentAgentError,
    RecruitmentAgentValidationError,
)
from app.ai.agents.recruitment.prompts import RECRUITMENT_AGENT_SYSTEM_PROMPT
from app.ai.agents.recruitment.schemas import (
    RecruitmentAgentAnswer,
    RecruitmentAgentRequest,
    RecruitmentAgentUsage,
)
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm.base import LLMProvider
from app.ai.orchestration.tool_roundtrip import run_tool_roundtrip
from app.ai.tools.exceptions import (
    ToolAuthorizationError,
    ToolExecutionError,
    ToolValidationError,
)
from app.ai.tools.interview_reads import (
    GetCandidateInterviewsTool,
    GetInterviewFeedbackTool,
    GetInterviewTool,
    GetUpcomingInterviewsTool,
    ListInterviewsTool,
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
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    ) -> None:
        self._llm = llm_provider
        self._max_output_tokens = max_output_tokens
        self._max_tool_calls = max_tool_calls
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

        answer = (result.final_content or "").strip()
        if not answer:
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
        )
