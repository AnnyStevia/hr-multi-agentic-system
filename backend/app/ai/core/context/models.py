from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIExecutionContext:
    """Authenticated identity facts for the AI layer (informational only).

    Does not grant permissions. Tool authorization is enforced later via
    Core HR services using these facts plus existing RBAC.
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
