"""Leave Agent — HR Q&A via authorized leave read tools."""

from __future__ import annotations

from app.ai.agents.leave.exceptions import LeaveAgentError, LeaveAgentValidationError
from app.ai.agents.leave.prompts import LEAVE_AGENT_SYSTEM_PROMPT
from app.ai.agents.leave.schemas import (
    LeaveAgentAnswer,
    LeaveAgentRequest,
    LeaveAgentUsage,
)
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm.base import LLMProvider
from app.ai.orchestration.tool_roundtrip import run_tool_roundtrip
from app.ai.tools.exceptions import (
    ToolAuthorizationError,
    ToolExecutionError,
    ToolValidationError,
)
from app.ai.tools.find_employees import FindEmployeesTool
from app.ai.tools.leave_reads import (
    GetLeaveBalanceTool,
    GetLeavePolicyTool,
    GetLeaveRequestTool,
    ListCurrentlyOnLeaveTool,
    ListLeaveRequestsTool,
    ListLeaveTypesTool,
    ListPendingLeaveRequestsTool,
)
from app.ai.tools.registry import ToolRegistry
from app.modules.employees.service import EmployeeService
from app.modules.leave.service import LeaveService

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_MAX_TOOL_CALLS = 8


class LeaveAgent:
    """HR leave assistant using ToolExecutor-authorized read tools only."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        leave_service: LeaveService,
        employee_service: EmployeeService,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    ) -> None:
        self._llm = llm_provider
        self._max_output_tokens = max_output_tokens
        self._max_tool_calls = max_tool_calls
        self._registry = ToolRegistry()
        self._registry.register(FindEmployeesTool(employee_service))
        self._registry.register(ListLeaveTypesTool(leave_service))
        self._registry.register(GetLeaveBalanceTool(leave_service))
        self._registry.register(GetLeaveRequestTool(leave_service))
        self._registry.register(ListLeaveRequestsTool(leave_service))
        self._registry.register(ListPendingLeaveRequestsTool(leave_service))
        self._registry.register(ListCurrentlyOnLeaveTool(leave_service))
        self._registry.register(GetLeavePolicyTool(leave_service))

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

        answer = (result.final_content or "").strip()
        if not answer:
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
        )
