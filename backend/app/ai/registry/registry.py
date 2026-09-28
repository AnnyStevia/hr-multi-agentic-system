"""Static agent registry — implemented agents only."""

from __future__ import annotations

from app.ai.registry.definitions import AgentDefinition

KNOWLEDGE_AGENT = AgentDefinition(
    id="knowledge",
    display_name="Knowledge",
    description=(
        "Answers questions grounded in company documents and HR policies "
        "via RAG. Read-only; no write tools."
    ),
    intents=(
        "company policy",
        "hr policy",
        "handbook",
        "company documents",
        "what does the handbook say",
        "according to our policy",
        "document",
        "policy documentation",
    ),
    required_permissions_any=frozenset({"company_documents:read"}),
    supports_confirmation=False,
)

LEAVE_AGENT = AgentDefinition(
    id="leave",
    display_name="Leave",
    description=(
        "Leave balances, requests, team pending leave, and confirmation-gated "
        "leave writes. Manager scope uses org chart, not an RBAC manager role."
    ),
    intents=(
        "leave",
        "vacation",
        "pto",
        "time off",
        "absence",
        "leave balance",
        "leave request",
        "pending leave",
        "approve leave",
        "reject leave",
        "cancel leave",
        "who is on leave",
    ),
    required_permissions_any=frozenset({"leaves:read"}),
    supports_confirmation=True,
)

RECRUITMENT_AGENT = AgentDefinition(
    id="recruitment",
    display_name="Recruitment",
    description=(
        "Jobs, applications, candidate fit, shortlist/reject, and interview "
        "reads/writes for HR and Admin."
    ),
    intents=(
        "candidate",
        "application",
        "cv screening",
        "shortlist",
        "reject candidate",
        "interview",
        "interviewer",
        "interview feedback",
        "hiring pipeline",
        "job applications",
        "candidate fit",
        "recruitment",
    ),
    required_permissions_any=frozenset({"recruitment:read"}),
    supports_confirmation=True,
)

ONBOARDING_AGENT = AgentDefinition(
    id="onboarding",
    display_name="Onboarding",
    description=(
        "Self and HR onboarding status, progress, and tasks; confirmation-gated "
        "acknowledgement, manual task completion, and force-complete. "
        "Availability uses employee_id or onboarding:read — not tool authorization."
    ),
    intents=(
        "onboarding",
        "onboarding progress",
        "onboarding tasks",
        "acknowledge onboarding task",
        "complete onboarding",
        "my onboarding",
        "onboarding checklist",
        "onboarding status",
        "pending onboarding tasks",
    ),
    required_permissions_any=frozenset({"onboarding:read"}),
    supports_confirmation=True,
)

# Implemented agents only. Training / Documents / Offboarding are not registered.
REGISTERED_AGENTS: tuple[AgentDefinition, ...] = (
    KNOWLEDGE_AGENT,
    LEAVE_AGENT,
    RECRUITMENT_AGENT,
    ONBOARDING_AGENT,
)

_AGENTS_BY_ID: dict[str, AgentDefinition] = {a.id: a for a in REGISTERED_AGENTS}


def get_agent_definition(agent_id: str) -> AgentDefinition | None:
    return _AGENTS_BY_ID.get(agent_id)


def list_registered_agents() -> tuple[AgentDefinition, ...]:
    return REGISTERED_AGENTS
