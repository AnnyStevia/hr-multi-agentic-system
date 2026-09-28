# Phase 9.2E — Register Onboarding in Unified Assistant

**Status:** Implemented. Registry + router + unified ask dispatch only. No new tools, permissions, migrations, or FE redesign.

Alembic head remains **`045_application_rejection_reason`**.

---

## Architecture

```text
POST /api/v1/ai/assistant/ask
  → AIExecutionContext
  → get_available_agents (registry)
  → route_message (deterministic keywords)
  → OnboardingAgent.ask (when agent_id=onboarding)
  → existing read/write tools → OnboardingService
  → envelope: agent_id=onboarding + pending_confirmation
```

Standalone endpoints unchanged:

- `POST /api/v1/ai/onboarding/ask`
- `POST /api/v1/ai/onboarding/confirm`

---

## Registry

[`ONBOARDING_AGENT`](../app/ai/registry/registry.py) is registered:

| Field | Value |
|-------|--------|
| `id` | `onboarding` |
| `display_name` | Onboarding |
| `required_permissions_any` | `{onboarding:read}` |
| `supports_confirmation` | `True` |

**Not registered:** Training, Documents, Offboarding.

---

## Availability (locked rule)

[`availability.py`](../app/ai/registry/availability.py) special-cases `agent.id == "onboarding"` only:

| Actor | Available? |
|-------|------------|
| User with `employee_id` | Yes (even without `onboarding:read`) |
| User with `onboarding:read` (HR/Admin) | Yes (even without `employee_id`) |
| Candidate (`employee_id` None, no `onboarding:read`) | No |

Other agents keep `permission_names ∩ required_permissions_any`.

**Security boundary:** Registry/router decide **availability + intent only**. Tool metadata and `OnboardingService` remain authoritative for what the user may read or write. Routing to Onboarding does not grant cross-employee access.

---

## Routing / ambiguity

[`router.py`](../app/ai/routing/router.py):

- `_ONBOARDING_KEYWORDS` — progress, tasks, acknowledge, complete onboarding, checklist, etc.
- **vs Knowledge:** strong policy markers (“what does … policy say”, handbook) **and** no onboarding-task markers (`acknowledge`, `my onboarding`, `onboarding task`, …) → prefer Knowledge when available.
- Task / acknowledge / onboarding-progress language → Onboarding even if “policy” appears.
- Leave vs Onboarding remains score-based (leave balance → leave; onboarding progress → onboarding).
- Unavailable-signal path includes registered onboarding when the user lacks availability.

Clarify copy in the unified gateway mentions onboarding among options.

---

## Unified dispatch

[`ai_assistant.py`](../app/api/v1/ai_assistant.py):

- `Depends(get_onboarding_agent)`
- `agent_id == "onboarding"` → `OnboardingAgent.ask` (errors mapped like Leave)
- Response: `agent_id="onboarding"`, `pending_confirmation` via `_pending_from`

Confirm remains on standalone `/ai/onboarding/confirm`. Frontend (9.2D) already routes confirm by message `agentId`.

---

## Frontend

No FE code changes in 9.2E. Verify existing:

- `AssistantAgentId` includes `"onboarding"`
- `confirmOnboardingAction` + `confirmPending` by `agentId`

---

## Limitations / non-goals

- No Training / Document / Offboarding agents
- No manager onboarding report scope
- No new permissions, tools, or business rules
- No LLM supervisor, chat history, Markdown redesign, streaming, migrations

**Stop after 9.2E.**

---

## Tests / acceptance

| Suite | Result |
|-------|--------|
| Registry + router unit | **27 passed** |
| Unified assistant integration + onboarding AI + related unit | **83 passed** |
| Leave agent unit | **passed** (part of leave/recruitment smoke) |
| Recruitment agent unit | Known soft-fail: `test_unauthorized_tool_call_surfaces_as_agent_error` (pre-existing; not fixed in 9.2E) |
| Frontend `tsc --noEmit` then `npm run build` | **exit 0** |
| Alembic head | **`045_application_rejection_reason`** |
