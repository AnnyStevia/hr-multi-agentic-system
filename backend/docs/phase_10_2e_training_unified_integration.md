# Phase 10.2E — Training Agent Unified Assistant Integration

**Status:** Implemented. Registry + router + unified ask dispatch only. No new tools, permissions, migrations, or FE redesign.

Alembic head remains **`048_employee_training_progress`**.

---

## Architecture

```text
User
 ↓
POST /api/v1/ai/assistant/ask
 ↓
AIExecutionContext
 ↓
Registry availability
 ↓
Deterministic router
 ↓
TrainingAgent.ask
 ↓
Existing training tools
 ↓
pending_confirmation (writes) → agent_id=training
 ↓
FE confirmPending by message.agentId
 ↓
POST /api/v1/ai/training/confirm
 ↓
TrainingService → PostgreSQL
```

Standalone endpoints unchanged:

- `POST /api/v1/ai/training/ask`
- `POST /api/v1/ai/training/confirm`

---

## Registry

[`TRAINING_AGENT`](../app/ai/registry/registry.py):

| Field | Value |
|-------|--------|
| `id` | `training` |
| `display_name` | Training Agent |
| `required_permissions_any` | `{training:read}` (metadata; availability is special-cased) |
| `supports_confirmation` | `True` |

---

## Availability (locked rule)

[`availability.py`](../app/ai/registry/availability.py) special-cases `agent.id == "training"`:

| Actor | Available? |
|-------|------------|
| User with `employee_id` | Yes |
| HR/Admin staff + `training:read` (even without `employee_id`) | Yes |
| Non-staff with `training:read` only and no `employee_id` | No |
| Pre-hire candidate | No |

**Security boundary:** Registry/router decide **availability + intent only**. Tool metadata and `TrainingService` remain authoritative. Routing to Training does not grant catalogue or assign rights.

---

## Routing / ambiguity

[`router.py`](../app/ai/routing/router.py):

- `_TRAINING_KEYWORDS` — assignments, my trainings, complete/assign training, catalogue, onboarding training, etc.
- `_TRAINING_VAGUE` — `course` / `courses` / `learning` alone do **not** route.
- **vs Knowledge:** policy/handbook markers without `_TRAINING_TASK_MARKERS` → Knowledge.
- **vs Onboarding:** score-based asymmetric phrases; `onboarding tasks` / progress stay Onboarding; assign/catalogue/complete-my-training prefer Training; true ties clarify.
- Unavailable Training intent for candidates surfaces as `unavailable`.

Clarify/unavailable copy in the unified gateway mentions training.

---

## Unified dispatch

[`ai_assistant.py`](../app/api/v1/ai_assistant.py):

- `Depends(get_training_agent)`
- `agent_id == "training"` → `TrainingAgent.ask`
- Response: `agent_id="training"`, `pending_confirmation` via `_pending_from`

Confirm remains on standalone `/ai/training/confirm`. Frontend (10.2D) already routes confirm by message `agentId`.

---

## Actor semantics

| Actor | Registry | Tools |
|-------|----------|-------|
| Employee | Available | Self reads + complete own (confirm); no HR catalogue/assign |
| Manager | Available | Own only; no team training; no assign |
| HR/Admin | Available | Catalogue/assignment reads; assign after confirm |
| Candidate (pre-hire) | Unavailable | — |
| Post-hire with `employee_id` | Available | Self only |

---

## Frontend

No FE code changes in 10.2E. Verify existing:

- `AssistantAgentId` includes `"training"`
- `confirmTrainingAction` + `confirmPending` by `agentId`

---

## Limitations / non-goals

- No manager team-training
- No catalogue CRUD / delete AI tools
- No unified `/ai/assistant/confirm`
- No LLM supervisor, new permissions, or migrations

**Stop after 10.2E.**

---

## Validation (this phase)

| Suite | Result |
|-------|--------|
| Registry + router + unified assistant | **53 passed** |
| Regression (Training AI/domain + registry/router/assistant + Onboarding/Leave/Recruitment units) | **177 passed**, **1 failed** — known pre-existing `test_unauthorized_tool_call_surfaces_as_agent_error` (untouched) |
| Frontend `tsc --noEmit` | **exit 0** |
| Frontend `npm run build` | **exit 0** |
| Alembic head | **`048_employee_training_progress`** |
