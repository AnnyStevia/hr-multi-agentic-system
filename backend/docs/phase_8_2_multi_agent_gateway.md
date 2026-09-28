# Phase 8.2 — Multi-Agent HR Assistant Gateway

**Status:** Implemented (backend only). Frontend path-based agent selection is unchanged.

## Architecture

```text
User
  ↓
POST /api/v1/ai/assistant/ask
  ↓
AIExecutionContext (existing JWT → context)
  ↓
get_available_agents(context)   ← registry + permissions only
  ↓
route_message(message, available)  ← deterministic keywords
  ↓
Existing KnowledgeAgent / LeaveAgent / RecruitmentAgent
  ↓
Existing tools → existing domain services → PostgreSQL
```

Existing per-agent endpoints remain:

- `POST /api/v1/ai/knowledge/ask`
- `POST /api/v1/ai/leave/ask` + `/confirm`
- `POST /api/v1/ai/recruitment/ask` + `/confirm`

There is **no** unified confirm endpoint. Writes still require the existing HMAC confirmation flow on Leave/Recruitment confirm routes.

## Registry

Module: [`app/ai/registry/`](../app/ai/registry/)

| File | Role |
|------|------|
| `definitions.py` | Frozen `AgentDefinition` |
| `registry.py` | Code catalog: knowledge, leave, recruitment only |
| `availability.py` | `get_available_agents(context)` |

Availability rule: agent is available iff  
`context.permission_names ∩ required_permissions_any` is non-empty.

| Agent | Permission | Confirmation |
|-------|------------|--------------|
| knowledge | `company_documents:read` | No |
| leave | `leaves:read` | Yes (existing) |
| recruitment | `recruitment:read` | Yes (existing) |

**Not registered:** Training, Onboarding, Documents (future phases).

Availability answers: *May this user invoke this agent?*  
It does **not** encode approve-leave, reject-candidate, hire, or cross-employee data rules.

Manager Leave scope remains `Employee.manager_id` / org chart inside Leave tools + `LeaveService`. The registry does **not** require an RBAC `"manager"` role for Leave.

## Routing

Module: [`app/ai/routing/`](../app/ai/routing/)

- Deterministic keyword scoring only (no Gemini / no LLM router in 8.2).
- Router receives **only available** agent definitions.
- Outcomes: `agent` | `clarify` | `unavailable`.
- Never executes tools, never queries business data, never grants permissions.

Notable rules:

- Handbook / policy / document phrasing + leave keywords → prefer **knowledge** when available.
- Strong recruitment keywords when recruitment is **not** available → `unavailable` (do not call RecruitmentAgent).
- Vague “interviews” alone with recruitment available → `clarification_required`.

## Unified endpoint

`POST /api/v1/ai/assistant/ask`

Auth: authenticated user + `get_ai_execution_context` (no agent-specific `require_permissions` on the gateway — availability filters instead).

Request:

```json
{ "message": "..." }
```

Response envelope:

```json
{
  "agent_id": "knowledge|leave|recruitment|null",
  "answer": "...",
  "citations": [],
  "pending_confirmation": null,
  "status": "completed|clarification_required|unavailable",
  "model": "...",
  "tool_names_called": [],
  "usage": null
}
```

- Knowledge → citations preserved from RAG.
- Leave / Recruitment → `pending_confirmation` preserved from existing agent payloads.
- Clarify / unavailable → `agent_id: null`, no agent invocation.

## Dispatch

Gateway imports existing FastAPI builders:

- `get_knowledge_agent`
- `get_leave_agent`
- `get_recruitment_agent`

and calls only the selected agent’s `.ask()`. No parallel agent implementations.

## Confirmation preservation

1. User asks via unified (or per-agent) ask  
2. Agent may return `pending_confirmation` (HMAC-bound)  
3. Frontend confirms via existing `/ai/leave/confirm` or `/ai/recruitment/confirm`  
4. Existing authorization + domain service + audit apply  

Phase 8.2 does not add a second confirmation mechanism.

## Security boundaries

| Layer | Owner |
|-------|--------|
| HTTP auth | `get_current_user` |
| Agent availability | Registry (`permission_names`) |
| Intent selection | Router (available IDs only) |
| Tool auth | Existing `ToolMetadata` + `authorize_tool` |
| Resource scope | Existing tools / self-team helpers |
| Domain rules | LeaveService / ApplicationService / interview services |

The gateway must never become an authorization bypass. Employee/manager recruitment intents never enter the RecruitmentAgent path.

## Known limitation (deferred)

Leave’s `find_employees` tool still requires `recruitment:read` in tool metadata. Phase 8.2 does **not** broaden that permission. Report only — do not redesign here.

## Frontend

Path-based selection in the FE remains interim. Backend unified ask is ready for a later FE migration phase.

## Non-goals (intentionally out of 8.2)

- FE redesign / removing path routing  
- LLM router  
- `GET /ai/agents`  
- Global merged ToolRegistry  
- DB migrations  
- Training / Onboarding / Documents agents  
- LeaveService / Recruitment / HMAC changes  
