# Phase O.6D — Offboarding Agent Controlled Write Actions

Confirmation-gated writes over existing `OffboardingService`. Domain rules (O.5 readiness, clearance actor stamps, task assignee checks, account deactivation) remain in the service — tools do not reimplement them.

## Tools

| Tool | Who | Service method |
|------|-----|----------------|
| `complete_offboarding_case` | HR/Admin + `offboarding:write` | `complete(case_id)` |
| `update_offboarding_clearance` | HR/Admin + `offboarding:write` | `update_clearance_item_for_hr(...)` |
| `update_offboarding_task` | Dual: HR start/complete/reopen; employee start/complete assigned only | matching `*_for_hr` / `*_for_user` |

Not exposed: skip, cancel, Meet, exit-interview schedule, direct AuthService calls.

## Confirmation

Shared HMAC tokens (`app.ai.confirmation`). Propose path does **not** mutate. Confirm:

1. Validate token (user + expiry + signature)
2. Re-authorize tool metadata
3. `execute_writes=True` → domain service
4. Audit `proposed` / `confirmed` / `executed` / `failed` via `ai_tool_action_audits`

Endpoints:

- `POST /api/v1/ai/offboarding/ask` — may return `pending_confirmation`
- `POST /api/v1/ai/offboarding/confirm` — `{ "confirmation_token": "..." }`
- Unified ask returns pending; FE Confirm calls the standalone confirm endpoint

## Authorization

- Employees: own assigned task start/complete only; **no** case complete; **no** clearance
- Managers/candidates: no HR writes unless independently HR-authorized
- Tool metadata + service remain authoritative

## Registry

`supports_confirmation=true` for Offboarding Agent.
