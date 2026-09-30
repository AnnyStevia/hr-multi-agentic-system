# Phase O.5 — Offboarding Finalization & Completion Rules

## 1. Purpose

Make `OffboardingCase` completion **authoritative on the backend**: a case may only move to `completed` when checklist, clearance, and exit-interview rules are satisfied.

## 2. Rules

Centralized in `OffboardingService.can_complete(case_id)` / `complete(case_id)`:

1. **Checklist** — every **required** task must be `completed` (same math as O.2 `required_complete`). **`skipped` does not count.**
2. **Clearance** — `is_clearance_complete` (O.3); `not_applicable` does not block.
3. **Exit interview** — if an active interview is `scheduled`, block. **No interview** or **cancelled-only** does not block. `completed` satisfies.

`complete()` locks the case with `SELECT FOR UPDATE`, rechecks `pending_clearance`, then applies rules.

## 3. Blocker response

HTTP 400 with string detail:

```text
Offboarding cannot be completed: <blocker1>; <blocker2>; ...
```

Readiness: `GET /api/v1/offboarding/{case_id}/can-complete` → `{ can_complete, blockers[] }` (`offboarding:read`).

## 4. Non-goals

No migration, AI, notifications, IT revoke, request-flow changes.
