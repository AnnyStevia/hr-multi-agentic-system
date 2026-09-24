from pydantic import BaseModel, Field
import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    BaseTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolExecutionError,
    ToolMetadata,
    ToolNotFoundError,
    ToolRegistrationError,
    ToolRegistry,
    ToolValidationError,
)


def _context(*, user_id: int = 1, employee_id: int | None = 10) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=employee_id,
        candidate_id=None,
    )


class EchoInput(BaseModel):
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1)


class EchoOutput(BaseModel):
    model_config = {"extra": "forbid"}

    echo: str
    user_id: int


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo a message with the authenticated user id"
    metadata = ToolMetadata(operation="read", operates_on_current_user=True)
    input_model = EchoInput
    output_model = EchoOutput

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, EchoInput)
        return EchoOutput(echo=args.message, user_id=context.user_id)


class BoomTool(BaseTool):
    name = "boom"
    description = "Always fails"
    metadata = ToolMetadata(operation="write")
    input_model = EchoInput
    output_model = EchoOutput

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        raise RuntimeError("simulated failure")


def test_register_get_and_list_tools():
    registry = ToolRegistry()
    tool = EchoTool()
    registry.register(tool)
    assert registry.get("echo") is tool
    assert [item.name for item in registry.list_tools()] == ["echo"]


def test_duplicate_registration_rejected():
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ToolRegistrationError, match="already registered"):
        registry.register(EchoTool())


def test_unknown_tool_lookup():
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError, match="Unknown tool"):
        registry.get("missing")


def test_executor_validates_arguments_and_returns_result():
    registry = ToolRegistry()
    registry.register(EchoTool())
    executor = ToolExecutor(registry)
    ctx = _context(user_id=42)

    result = executor.execute(ctx, "echo", {"message": "hello"})

    assert result.success is True
    assert result.tool_name == "echo"
    assert result.error is None
    assert result.data == {"echo": "hello", "user_id": 42}


def test_executor_rejects_invalid_arguments():
    registry = ToolRegistry()
    registry.register(EchoTool())
    executor = ToolExecutor(registry)

    with pytest.raises(ToolValidationError, match="Invalid arguments"):
        executor.execute(_context(), "echo", {"message": ""})

    with pytest.raises(ToolValidationError):
        executor.execute(_context(), "echo", {"message": "ok", "extra": True})


def test_executor_requires_context():
    registry = ToolRegistry()
    registry.register(EchoTool())
    executor = ToolExecutor(registry)

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        executor.execute(None, "echo", {"message": "hello"})


def test_executor_wraps_tool_failures():
    registry = ToolRegistry()
    registry.register(BoomTool())
    executor = ToolExecutor(registry)

    with pytest.raises(ToolExecutionError, match="Tool 'boom' failed"):
        executor.execute(_context(), "boom", {"message": "hello"})


def test_tool_uses_context_identity_not_argument_claims():
    """Identity for the result comes from context, not forged argument fields."""

    class ClaimInput(BaseModel):
        model_config = {"extra": "forbid"}
        message: str
        # Attackers might try to pass user_id; forbid extra, and tool ignores any claim.

    class ClaimTool(BaseTool):
        name = "claim_echo"
        description = "Uses context.user_id only"
        metadata = ToolMetadata(operation="read", operates_on_current_user=True)
        input_model = ClaimInput
        output_model = EchoOutput

        def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
            assert isinstance(args, ClaimInput)
            return EchoOutput(echo=args.message, user_id=context.user_id)

    registry = ToolRegistry()
    registry.register(ClaimTool())
    executor = ToolExecutor(registry)
    result = executor.execute(
        _context(user_id=7),
        "claim_echo",
        {"message": "hi"},
    )
    assert result.data is not None
    assert result.data["user_id"] == 7
