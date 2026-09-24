"""Unit tests for AI tool authorization (roles, permissions, current-user scope)."""

from pydantic import BaseModel, Field
import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    BaseTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolMetadata,
    ToolRegistry,
)


def _context(
    *,
    user_id: int = 1,
    role_names: frozenset[str] | None = None,
    permission_names: frozenset[str] | None = None,
    employee_id: int | None = 10,
    candidate_id: int | None = None,
) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=role_names if role_names is not None else frozenset({"employee"}),
        permission_names=(
            permission_names
            if permission_names is not None
            else frozenset({"leaves:read"})
        ),
        employee_id=employee_id,
        candidate_id=candidate_id,
    )


class SimpleInput(BaseModel):
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1)


class IdentityInput(BaseModel):
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1)
    user_id: int | None = None
    employee_id: int | None = None
    candidate_id: int | None = None


class SimpleOutput(BaseModel):
    model_config = {"extra": "forbid"}

    echo: str


class _SpyMixin:
    executed = False

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        type(self).executed = True
        assert isinstance(args, (SimpleInput, IdentityInput))
        return SimpleOutput(echo=args.message)


class RoleGatedTool(_SpyMixin, BaseTool):
    name = "role_gated"
    description = "Requires hr or admin role"
    metadata = ToolMetadata(
        operation="read",
        required_roles=frozenset({"hr", "admin"}),
    )
    input_model = SimpleInput
    output_model = SimpleOutput


class PermissionGatedTool(_SpyMixin, BaseTool):
    name = "perm_gated"
    description = "Requires leaves:read and leaves:write"
    metadata = ToolMetadata(
        operation="write",
        required_permissions=frozenset({"leaves:read", "leaves:write"}),
    )
    input_model = SimpleInput
    output_model = SimpleOutput


class CurrentUserTool(_SpyMixin, BaseTool):
    name = "current_user"
    description = "Self-scoped tool"
    metadata = ToolMetadata(operation="read", operates_on_current_user=True)
    input_model = IdentityInput
    output_model = SimpleOutput


class ConfirmMetaTool(_SpyMixin, BaseTool):
    name = "confirm_meta"
    description = "Write tool that may need confirmation later"
    metadata = ToolMetadata(
        operation="write",
        may_require_confirmation=True,
        required_permissions=frozenset({"leaves:write"}),
    )
    input_model = SimpleInput
    output_model = SimpleOutput


@pytest.fixture(autouse=True)
def _reset_spy_flags():
    RoleGatedTool.executed = False
    PermissionGatedTool.executed = False
    CurrentUserTool.executed = False
    ConfirmMetaTool.executed = False
    yield


def test_authorize_success_with_valid_role():
    tool = RoleGatedTool()
    ctx = _context(role_names=frozenset({"hr"}))
    registry = ToolRegistry()
    registry.register(tool)
    out = ToolExecutor(registry).execute(ctx, "role_gated", {"message": "ok"})
    assert out.success is True
    assert RoleGatedTool.executed is True


def test_authorize_success_with_valid_permissions():
    tool = PermissionGatedTool()
    ctx = _context(
        permission_names=frozenset({"leaves:read", "leaves:write", "documents:read"})
    )
    registry = ToolRegistry()
    registry.register(tool)
    out = ToolExecutor(registry).execute(ctx, "perm_gated", {"message": "ok"})
    assert out.success is True
    assert PermissionGatedTool.executed is True


def test_authorize_success_current_user_matching_and_omitted_identity():
    tool = CurrentUserTool()
    ctx = _context(user_id=5, employee_id=50, candidate_id=None)
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    omitted = executor.execute(ctx, "current_user", {"message": "self"})
    assert omitted.success is True

    matching = executor.execute(
        ctx,
        "current_user",
        {"message": "self", "user_id": 5, "employee_id": 50},
    )
    assert matching.success is True
    assert CurrentUserTool.executed is True


def test_authorize_failure_missing_role():
    tool = RoleGatedTool()
    ctx = _context(role_names=frozenset({"employee"}))
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        ToolExecutor(registry).execute(ctx, "role_gated", {"message": "nope"})
    assert RoleGatedTool.executed is False


def test_authorize_failure_missing_permission():
    tool = PermissionGatedTool()
    ctx = _context(permission_names=frozenset({"leaves:read"}))  # missing leaves:write
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        ToolExecutor(registry).execute(ctx, "perm_gated", {"message": "nope"})
    assert PermissionGatedTool.executed is False


def test_authorize_failure_current_user_identity_mismatch():
    tool = CurrentUserTool()
    ctx = _context(user_id=5, employee_id=50)
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        executor.execute(
            ctx,
            "current_user",
            {"message": "spy", "user_id": 99},
        )
    assert CurrentUserTool.executed is False

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        executor.execute(
            ctx,
            "current_user",
            {"message": "spy", "employee_id": 999},
        )
    assert CurrentUserTool.executed is False


def test_authorize_failure_candidate_identity_mismatch():
    tool = CurrentUserTool()
    ctx = _context(user_id=3, employee_id=None, candidate_id=20)
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        ToolExecutor(registry).execute(
            ctx,
            "current_user",
            {"message": "spy", "candidate_id": 21},
        )
    assert CurrentUserTool.executed is False


def test_authorize_failure_missing_context():
    tool = CurrentUserTool()
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        ToolExecutor(registry).execute(None, "current_user", {"message": "hi"})
    assert CurrentUserTool.executed is False


def test_unauthorized_tool_never_executed():
    tool = RoleGatedTool()
    registry = ToolRegistry()
    registry.register(tool)
    assert RoleGatedTool.executed is False

    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _context(role_names=frozenset({"candidate"})),
            "role_gated",
            {"message": "x"},
        )
    assert RoleGatedTool.executed is False


def test_authorization_happens_after_validation_before_execution():
    """Invalid args fail as validation; auth deny never reaches execute."""

    class OrderTool(BaseTool):
        name = "order"
        description = "Tracks call order"
        metadata = ToolMetadata(
            operation="read",
            required_roles=frozenset({"admin"}),
        )
        input_model = SimpleInput
        output_model = SimpleOutput
        executed = False

        def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
            OrderTool.executed = True
            return SimpleOutput(echo="should-not-run")

    registry = ToolRegistry()
    registry.register(OrderTool())
    executor = ToolExecutor(registry)
    ctx = _context(role_names=frozenset({"employee"}))

    from app.ai.tools import ToolValidationError

    with pytest.raises(ToolValidationError):
        executor.execute(ctx, "order", {"message": ""})
    assert OrderTool.executed is False

    with pytest.raises(ToolAuthorizationError):
        executor.execute(ctx, "order", {"message": "valid"})
    assert OrderTool.executed is False


def test_llm_supplied_identity_cannot_override_authenticated_identity():
    tool = CurrentUserTool()
    ctx = _context(user_id=1, employee_id=10)
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            ctx,
            "current_user",
            {"message": "leave balance for B", "user_id": 2, "employee_id": 20},
        )
    assert CurrentUserTool.executed is False


def test_may_require_confirmation_echoed_without_blocking():
    tool = ConfirmMetaTool()
    ctx = _context(permission_names=frozenset({"leaves:write"}))
    registry = ToolRegistry()
    registry.register(tool)

    result = ToolExecutor(registry).execute(ctx, "confirm_meta", {"message": "submit"})
    assert result.success is True
    assert result.may_require_confirmation is True
    assert ConfirmMetaTool.executed is True


def test_role_or_semantics_any_one_role_suffices():
    tool = RoleGatedTool()
    ctx = _context(role_names=frozenset({"admin", "employee"}))
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutor(registry).execute(ctx, "role_gated", {"message": "ok"})
    assert result.success is True
