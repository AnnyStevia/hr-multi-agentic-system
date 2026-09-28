# Phase 9.2D — Onboarding Agent Hardening & FE Confirm Integration

**Stance:** No new onboarding business capabilities. Harden write/confirm guarantees; keep `_infer_target` generic; wire frontend `agentId`-based onboarding confirm. **No** registry, unified ask routing, or Alembic migrations.

Alembic head remains **`045_application_rejection_reason`**.

---

## Hardened write / confirmation guarantees

Shared HMAC confirmation (same as Leave/Recruitment):

1. Ask → `execute_writes=False` → `pending_confirmation` (token bound to user, tool, exact args, target).
2. Confirm → `verify_confirmation_token` → `execute_writes=True` → `OnboardingService`.
3. Rejects: wrong user, forged/tampered body (e.g. altered `task_id`), wrong tool name (not in onboarding registry), expired token.
4. Replay after success: token still verifies; domain rejects already-completed (no single-use `jti` — same as Leave/Recruitment).
5. Audit: `proposed` → `confirmed` → `executed` | `failed` (`invalid_or_expired_token`, `unknown_tool`, `execution`, …).
6. Pending is **not** execution — service is not called until confirm.

Small agent hardening: `confirm()` maps `ToolNotFoundError` → validation + `failed`/`unknown_tool` audit (wrong-tool tokens).

---

## `_infer_target`

[`executor.py`](../app/ai/tools/executor.py) maps argument **field names** only (`task_id` → `onboarding_task`, `onboarding_id` → `onboarding`, `request_id` → `leave_request`). No onboarding authorization or domain rules in the executor. Leave `request_id` mapping unchanged (regression asserted).

---

## Authorization matrix (unchanged)

| Actor | Own reads | Own ACK write | HR reads/writes |
|-------|-----------|---------------|-----------------|
| Employee | Yes | Yes (confirm) | Deny |
| Manager | Own only | Own ACK only | Deny (no reports) |
| HR/Admin | N/A | N/A | Yes (confirm for writes) |
| Candidate | Deny | Deny | Deny |

---

## Write-intent (prompt)

Hypothetical / advice (“What happens if…”, “Should I…”) → reads only.  
Imperative ACK/manual/complete → write → `pending_confirmation`.  
Never claim success before confirm execution. Prompt is **not** the security layer.

---

## Frontend confirmation plumbing

| Change | Detail |
|--------|--------|
| `AssistantAgentId` | Includes `"onboarding"` |
| `api.confirmOnboardingAction` | `POST /api/v1/ai/onboarding/confirm` |
| `confirmPending` | Routes by **message `agentId`**, not pathname |

**Known limit:** Unified `askAssistant` cannot yet return `agent_id: "onboarding"` until Phase **9.2E** registry registration. Confirm plumbing is ready for messages that already carry `agentId: "onboarding"`. Standalone backend `POST /ai/onboarding/ask` + `/confirm` remain the full E2E path today.

Navigation while pending: pathname only closes the panel; messages (and `agentId` + pending token) are retained — confirm still hits onboarding endpoint.

---

## Explicit non-goals

Registry / routing / unified ask, Training/Document/Offboarding, manager scope, CRUD/create/backfill/sync, chat history, Markdown redesign, streaming, migrations.

---

## Tests

| Suite | Result |
|-------|--------|
| Onboarding writes + agent + integration + leave unit/writes + leave write integration | **92 passed** |
| Frontend `tsc --noEmit` | **exit 0** |
| Frontend `npm run build` | **exit 0** |

Known pre-existing: Recruitment `test_unauthorized_tool_call_surfaces_as_agent_error` (soft-fail expectation drift) — not “fixed” in 9.2D.
