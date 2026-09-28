# Phase 8.3B — Unified HR Assistant Frontend Integration

**Stance:** Frontend-only migration to `POST /api/v1/ai/assistant/ask`. No backend changes.

## What changed

| Area | Change |
|------|--------|
| Types | `AssistantAskPayload` / `AssistantAskResponse` / `AssistantAgentId` / `AssistantAskStatus`; `AIChatMessage.agentId` |
| API | `api.askAssistant({ message })` → unified gateway |
| Hook | `ask()` always calls unified ask; soft statuses rendered as normal messages |
| Confirm | Routes by `message.agentId` → `/ai/leave/confirm` or `/ai/recruitment/confirm` |
| Path routing | **Removed** — `resolveAgentMode` deleted; path no longer selects an agent |
| UI copy | Neutral HR Assistant welcome / composer / loading |
| Conversation | No longer cleared when navigating between HR/Employee pages; panel still closes on pathname change |

## Confirmation (critical)

```text
unified ask → pending_confirmation + agent_id on message
  → Confirm → message.agentId === "leave" | "recruitment"
  → existing confirm endpoints only
```

Knowledge never confirms writes. Missing `agentId` on a pending message shows a safe client error.

## Kept for compatibility

- Leave/Recruitment confirm methods unchanged (`confirmLeaveAction`, `confirmRecruitmentAction`).
- Per-agent ask clients (`askKnowledgeAgent` / `askLeaveAgent` / `askRecruitmentAgent`) were **removed in Phase 8.3C** after confirming zero runtime usages.

## Non-goals (deferred)

- Unified confirm endpoint
- Agent selector / last-response agent chip
- Markdown, chat history, Training/Onboarding/Documents agents
