from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from app.ai.core.context import AIExecutionContext

ToolOperation = Literal["read", "write"]


@dataclass(frozen=True)
class ToolMetadata:
    """Declarative tool metadata for later authorization (not enforced yet)."""

    operation: ToolOperation
    required_roles: frozenset[str] = field(default_factory=frozenset)
    required_permissions: frozenset[str] = field(default_factory=frozenset)
    operates_on_current_user: bool = False
    may_require_confirmation: bool = False


class BaseTool(ABC):
    """Provider-agnostic AI tool. Concrete tools must call Core HR services only."""

    name: str
    description: str
    metadata: ToolMetadata
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    @abstractmethod
    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        """Run the tool using authenticated context and validated arguments."""
        raise NotImplementedError
