# Phase Chat History — Implementation

**Status:** Implemented (unified assistant only).  
**Design source:** [`phase_chat_history_audit.md`](phase_chat_history_audit.md).  
**Prerequisite:** Orc.1–Orc.4 (LangGraph behind `/ai/assistant/ask`).

This phase adds persistent, user-owned chat history around the unified ask path. It does **not** redesign LangGraph, specialists, `AIExecutionContext`, HMAC confirm, DocumentAIPanel, or `ai_tool_action_audits`.

---

## Schema

Migration: [`054_ai_chat_history.py`](../alembic/versions/054_ai_chat_history.py)  
(`down_revision = 053_offboarding_exit_interview`)

### `ai_conversations`

| Column | Notes |
|--------|-------|
| `id` | Integer PK |
| `user_id` | FK → `users.id` ON DELETE CASCADE (ownership ACL) |
| `employee_id` / `candidate_id` | Optional snapshots at create; **not** ACL |
| `title` | Truncated first user message (≤80 chars stored up to 200) |
| `created_at` / `updated_at` | Timezone-aware |

Index: `(user_id, updated_at)` plus `user_id`.

### `ai_conversation_messages`

| Column | Notes |
|--------|-------|
| `id` | Integer PK |
| `conversation_id` | FK CASCADE |
| `role` | `user` \| `assistant` |
| `content` | User text / assistant answer |
| `sequence` | Monotonic per conversation; `UNIQUE(conversation_id, sequence)` |
| `agent_id`, `status`, `route_reason`, `node_path` | Safe orchestration metadata |
| `tool_names_called` | JSON list of names only |
| `citations_json` | Sanitized Knowledge metadata only |
| `pending_tool_name`, `pending_summary`, `pending_expires_at` | Display-safe pending |
| `pending_token_digest` | SHA-256 of live token; **never** raw token |
| `pending_resolved` | Updated by confirm hooks |
| `model`, `usage_json` | Optional |
| `created_at` | |

Index: `(conversation_id, created_at)`.

### Sequence strategy

1. `SELECT … FOR UPDATE` the conversation row (ownership-scoped).  
2. `MAX(sequence)+1` (or 1).  

Avoids unlocked concurrent append races; simple and Postgres-friendly. SQLite tests treat `FOR UPDATE` as a no-op.

---

## Package layout

[`app/ai/history/`](../app/ai/history/):

| Module | Role |
|--------|------|
| `models.py` | ORM |
| `repository.py` | Ownership-scoped queries + lock/sequence |
| `service.py` | begin_turn / append / resolve / CRUD |
| `schemas.py` | API DTOs (never expose digest or tokens) |
| `sanitize.py` | Citation sanitizer + `token_digest` / title |
| `hooks.py` | Best-effort `resolve_pending` for confirm handlers |

---

## Ownership / IDOR

- Owner = `user_id` from `AIExecutionContext` / authenticated user.  
- List / get / delete / append / ask-with-id all filter `conversation.user_id == current user`.  
- Missing or foreign `conversation_id` → **404**.  
- No HR/Admin cross-user chat access in this MVP.

---

## Ask lifecycle

`POST /api/v1/ai/assistant/ask`

1. Auth + frozen `AIExecutionContext` unchanged.  
2. Optional `conversation_id` on body (`extra=forbid` still).  
3. If null → create conversation (title from first message); else load+lock with ownership → 404 if foreign.  
4. Append **user** message.  
5. Run existing `run_assistant_orchestration` (unchanged).  
6. Soft success path → append **assistant** message (safe fields; pending → digest + summary + expiry + `pending_resolved=false`).  
7. Response envelope **adds** `conversation_id` + assistant `message_id`. Live `pending_confirmation.token` still returned for FE Confirm.  
8. Without `conversation_id` the server still creates a thread so IDs are always returned when persistence succeeds (backward compatible body `{message}`).

**Hard failures:** when a conversation was opened, persist a short assistant `status=error` stub (no stack traces/secrets), then raise the same HTTP errors as before.

**History DB failure after successful ask:** log; still return **200** ask response (do not retry domain tools; do not fail confirmability). Orchestration/domain writes remain authoritative.

---

## Confirm relationship

Confirm stays on specialist routes:

- `POST /ai/leave/confirm`
- `POST /ai/recruitment/confirm`
- `POST /ai/onboarding/confirm`
- `POST /ai/training/confirm`
- `POST /ai/offboarding/confirm`

After success **or** handled failure, handlers call `resolve_pending_best_effort(db, user_id, token, resolved=True)`:

- Digests the token, finds owned message by digest, sets `pending_resolved`.  
- Confirm **must succeed** even if no history row exists.  
- History failures are logged and never undo domain writes.

Confirm is **not** resumable from DB: hydrated history shows pending summary only; Confirm buttons require a live in-memory token from the current ask response.

---

## History CRUD APIs

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/ai/conversations` | Current user’s summaries |
| `GET` | `/api/v1/ai/conversations/{id}` | Detail + messages (safe fields) |
| `DELETE` | `/api/v1/ai/conversations/{id}` | Cascade messages; 404 if foreign |

Response messages expose `pending` as `{tool_name, summary, expires_at, resolved}` — never token or digest.

---

## Frontend (minimal)

- `conversation_id` kept in React state + `sessionStorage`.  
- Ask sends optional `conversation_id`; stores returned id.  
- On load/open, hydrate via `GET /ai/conversations/{id}` when an id is stored.  
- Live pending → Confirm/Cancel as before.  
- Historical pending → text only (`pendingHistorical`), **no** Confirm.  
- DocumentAIPanel unchanged (no history).

---

## Security rules (enforced)

| Never store | Store |
|-------------|--------|
| Raw confirmation token | SHA-256 digest + summary/expiry |
| Tool arguments / write payloads | Tool **names** only |
| Document/CV excerpts, storage keys, RAG chunks | Knowledge citation metadata (sanitized) |
| JWT/secrets | — |

`ai_tool_action_audits` remains the authoritative write audit trail.

---

## Tests

| Suite | Coverage |
|-------|----------|
| `test_ai_chat_history_sanitize.py` | Citation stripping, digest, title |
| `test_ai_chat_history_service.py` | Sequence, ownership 404, digest-only pending, resolve/foreign/no-row, cascade delete |
| `test_ai_chat_history.py` | Ask create/continue, foreign 404, pending digest vs live token, confirm resolve + orphan confirm, list/delete |

Regression: existing assistant/orchestration and leave/recruitment/onboarding/training/offboarding confirm suites; FE `tsc` + `npm run build`.

---

## Limitations

- Single active thread continuity via `sessionStorage` (no full conversation browser UI).  
- No DocumentAIPanel / standalone agent history.  
- No cross-user (HR) read of another user’s assistant thread.  
- Confirm cannot be completed from hydrated history alone.  
- Retention / purge policy not implemented beyond user delete + user CASCADE.  
- See audit doc for deferred items (handoffs, richer retention, multi-thread UI).
