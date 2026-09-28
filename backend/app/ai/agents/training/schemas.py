"""Training Agent request/response schemas (reads + confirmation-gated writes)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context import AIExecutionContext


class TrainingAgentUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class TrainingAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    question: str = Field(min_length=1, max_length=4000)
    context: AIExecutionContext


class PendingConfirmationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    tool_name: str
    summary: str
    expires_at: int


class TrainingAgentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: TrainingAgentUsage | None = None
    pending_confirmation: PendingConfirmationInfo | None = None
