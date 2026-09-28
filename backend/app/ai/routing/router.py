"""Deterministic keyword router — no LLM, no tools, no authorization."""

from __future__ import annotations

from collections.abc import Sequence

from app.ai.registry.definitions import AgentDefinition
from app.ai.registry.registry import REGISTERED_AGENTS
from app.ai.routing.schemas import RouteDecision

# Strong synonym / keyword sets used for scoring (routing hints only).
_KNOWLEDGE_KEYWORDS: tuple[str, ...] = (
    "company policy",
    "hr policy",
    "employee handbook",
    "handbook",
    "company document",
    "company documents",
    "according to our policy",
    "according to the policy",
    "according to the handbook",
    "what does the handbook",
    "policy documentation",
    "policy say",
    "policies say",
    "document say",
    "documents say",
)

_LEAVE_KEYWORDS: tuple[str, ...] = (
    "leave balance",
    "leave request",
    "pending leave",
    "approve leave",
    "reject leave",
    "cancel leave",
    "who is on leave",
    "on leave",
    "time off",
    "annual leave",
    "sick leave",
    "vacation",
    "pto",
    "absence",
    "leave days",
    "remaining leave",
    "my leave",
    "team leave",
    "leave",
)

_RECRUITMENT_STRONG: tuple[str, ...] = (
    "reject candidate",
    "shortlist",
    "cv screening",
    "candidate fit",
    "hiring pipeline",
    "job application",
    "job applications",
    "interview feedback",
    "interview invitation",
    "recruitment",
    "candidate",
    "application",
    "interviewer",
)

# Vague recruitment-adjacent terms that alone are not enough to route.
_RECRUITMENT_VAGUE: tuple[str, ...] = (
    "interview",
    "interviews",
)

_ONBOARDING_KEYWORDS: tuple[str, ...] = (
    "onboarding progress",
    "onboarding checklist",
    "onboarding status",
    "onboarding tasks",
    "onboarding task",
    "pending onboarding",
    "acknowledge task",
    "acknowledge my",
    "complete onboarding",
    "my onboarding",
    "onboarding",
)

# Task / ack language that keeps routing on Onboarding even if "policy" appears.
_ONBOARDING_TASK_MARKERS: tuple[str, ...] = (
    "acknowledge",
    "onboarding task",
    "onboarding tasks",
    "my onboarding",
    "onboarding progress",
    "onboarding checklist",
    "onboarding status",
    "complete onboarding",
    "pending onboarding",
)

_KNOWLEDGE_POLICY_MARKERS: tuple[str, ...] = (
    "handbook",
    "according to our policy",
    "according to the policy",
    "according to the handbook",
    "company policy",
    "hr policy",
    "policy documentation",
    "what does the handbook",
    "company document",
    "company documents",
)

# Strong policy-document phrasing used vs Onboarding ambiguity.
_KNOWLEDGE_VS_ONBOARDING_MARKERS: tuple[str, ...] = (
    *_KNOWLEDGE_POLICY_MARKERS,
    "policy say",
    "policies say",
    "document say",
    "documents say",
)


def _normalize(message: str) -> str:
    return " ".join(message.lower().split())


def _score_keywords(text: str, keywords: Sequence[str]) -> int:
    """Score by longest matching phrases first; count distinct hits."""
    score = 0
    matched_spans: list[tuple[int, int]] = []
    for kw in sorted(keywords, key=len, reverse=True):
        start = 0
        while True:
            idx = text.find(kw, start)
            if idx < 0:
                break
            end = idx + len(kw)
            # Avoid double-counting overlapping matches of shorter keywords.
            if any(not (end <= s or idx >= e) for s, e in matched_spans):
                start = idx + 1
                continue
            matched_spans.append((idx, end))
            # Longer phrases weigh more.
            score += max(1, len(kw.split()))
            start = end
    return score


def _has_any(text: str, phrases: Sequence[str]) -> bool:
    return any(p in text for p in phrases)


def _score_agent(agent_id: str, text: str) -> int:
    if agent_id == "knowledge":
        base = _score_keywords(text, _KNOWLEDGE_KEYWORDS)
        # Also score registered intents as soft hits.
        return base
    if agent_id == "leave":
        return _score_keywords(text, _LEAVE_KEYWORDS)
    if agent_id == "recruitment":
        strong = _score_keywords(text, _RECRUITMENT_STRONG)
        vague = _score_keywords(text, _RECRUITMENT_VAGUE)
        # Vague-only (e.g. "Tell me about interviews") is not a strong match.
        if strong == 0 and vague > 0:
            return 0
        return strong + vague
    if agent_id == "onboarding":
        return _score_keywords(text, _ONBOARDING_KEYWORDS)
    return 0


def _unavailable_agent_signal(text: str, available_ids: set[str]) -> str | None:
    """If the message clearly targets a registered but unavailable agent, return its id."""
    for agent in REGISTERED_AGENTS:
        if agent.id in available_ids:
            continue
        score = _score_agent(agent.id, text)
        # Recruitment vague-only should not count as unavailable signal when
        # recruitment is missing — still "unavailable" if strong recruitment terms.
        if agent.id == "recruitment":
            if _score_keywords(text, _RECRUITMENT_STRONG) > 0:
                return agent.id
            continue
        if score > 0:
            return agent.id
    return None


def route_message(
    message: str,
    available: Sequence[AgentDefinition],
) -> RouteDecision:
    """Select exactly one available agent, or clarify / unavailable.

    Only ``available`` agents are scored for selection. Unavailable agents are
    never returned as ``agent``.
    """
    text = _normalize(message)
    if not text:
        return RouteDecision(
            kind="clarify",
            agent_id=None,
            reason="empty_message",
        )

    available_list = list(available)
    available_ids = {a.id for a in available_list}

    if not available_list:
        return RouteDecision(
            kind="unavailable",
            agent_id=None,
            reason="no_available_agents",
        )

    # Case B: handbook/policy + leave wording → prefer Knowledge when available.
    if (
        "knowledge" in available_ids
        and _has_any(text, _KNOWLEDGE_POLICY_MARKERS)
        and _score_keywords(text, _LEAVE_KEYWORDS) > 0
    ):
        return RouteDecision(
            kind="agent",
            agent_id="knowledge",
            reason="policy_document_preference",
        )

    # Policy/handbook Qs without onboarding task/ack language → Knowledge
    # (even if the word "onboarding" appears in a policy question).
    if (
        "knowledge" in available_ids
        and _has_any(text, _KNOWLEDGE_VS_ONBOARDING_MARKERS)
        and not _has_any(text, _ONBOARDING_TASK_MARKERS)
        and _score_keywords(text, _ONBOARDING_KEYWORDS) > 0
    ):
        return RouteDecision(
            kind="agent",
            agent_id="knowledge",
            reason="policy_document_preference",
        )

    scores: dict[str, int] = {
        agent.id: _score_agent(agent.id, text) for agent in available_list
    }

    # Case E: vague "interviews" with recruitment available and no strong other hit.
    if (
        "recruitment" in available_ids
        and _score_keywords(text, _RECRUITMENT_STRONG) == 0
        and _has_any(text, _RECRUITMENT_VAGUE)
        and all(s == 0 for aid, s in scores.items() if aid != "recruitment")
    ):
        return RouteDecision(
            kind="clarify",
            agent_id=None,
            reason="ambiguous_interview_context",
        )

    strong = {aid: s for aid, s in scores.items() if s > 0}
    if len(strong) == 1:
        agent_id = next(iter(strong))
        return RouteDecision(
            kind="agent",
            agent_id=agent_id,
            reason="single_intent_match",
        )

    if len(strong) > 1:
        # Prefer the highest score; if tied, clarify.
        best = max(strong.values())
        winners = [aid for aid, s in strong.items() if s == best]
        if len(winners) == 1:
            return RouteDecision(
                kind="agent",
                agent_id=winners[0],
                reason="highest_intent_score",
            )
        return RouteDecision(
            kind="clarify",
            agent_id=None,
            reason="multiple_intent_matches",
        )

    # No match among available — check unavailable intent (Case D).
    blocked = _unavailable_agent_signal(text, available_ids)
    if blocked is not None:
        return RouteDecision(
            kind="unavailable",
            agent_id=None,
            reason=f"intent_requires_unavailable_agent:{blocked}",
        )

    return RouteDecision(
        kind="clarify",
        agent_id=None,
        reason="no_intent_match",
    )
