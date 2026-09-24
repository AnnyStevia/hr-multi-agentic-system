from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIExecutionContext:
    """Authenticated identity facts for the AI layer.

    Built only from JWT/DB identity — never from LLM claims.
    Tool authorization reads these facts against ToolMetadata using Core HR RBAC semantics.
    """

    user_id: int
    role_names: frozenset[str]
    permission_names: frozenset[str]
    employee_id: int | None
    candidate_id: int | None

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names

    def has_any_role(self, *role_names: str) -> bool:
        return bool(self.role_names.intersection(role_names))
