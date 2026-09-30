# Phase Chat History — Architecture Audit

**Status:** Audit only (no code, migrations, or dependency changes).  
**Prerequisite:** Orc.1–Orc.4 complete (LangGraph behind unified ask; empty handoff allowlist; chat-history schema sketched in Orc.4).  
**Next phase:** implementation of persistent chat history per this document.

Related: [`phase_orc_4_handoffs_and_chat_history.md`](phase_orc_4_handoffs_and_chat_history.md), [`phase_orc_1_langgraph_orchestration.md`](phase_orc_1_langgraph_orchestration.md).

---

## Document map

| Section | Content |
|---------|---------|
| **CURRENT STATE** | §§1–4 — orchestration, contracts, agents, tools/audit |
| **PROPOSED STATE** | §§7–10, §12–13 — model, lifecycle, LangGraph vs DB, FE |
| **SECURITY DECISIONS** | §§5–6, §11, §14 — classification, ownership, retention, tests |
| **IMPLEMENTATION PLAN** | §15 — locked recommendation + later work |

---

# CURRENT STATE

## 1. Current orchestration

### Data flow (one ask)

```text
User message (FE)
  → POST /api/v1/ai/assistant/ask  { message }
  → get_current_user + get_ai_execution_context  (frozen AIExecutionContext)
  → Depends-injected specialist instances (Knowledge…Offboarding)
  → run_assistant_orchestration(...)
       LangGraph:
         filter_available  → get_available_agents(context)
         select_agent      → route_message(message, available)   [deterministic]
         maybe_llm_clarify → optional; ai_orchestrator_llm_clarify default false
         invoke_specialist → exactly one XxxAgent.ask(...)
         maybe_allowlisted_handoff → no-op (ALLOWLISTED_HANDOFFS empty)
         normalize_envelope → soft outcomes clear agent_id / pending
  → AssistantAskResponse envelope → FE
```

Confirm is **not** in this graph. FE Confirm → `POST /api/v1/ai/{leave|recruitment|onboarding|training|offboarding}/confirm`.

### Graph package

| Path | Role |
|------|------|
| [`app/ai/orchestration/graph/state.py`](../app/ai/orchestration/graph/state.py) | `OrchestratorState` TypedDict |
| [`app/ai/orchestration/graph/nodes.py`](../app/ai/orchestration/graph/nodes.py) | availability, route, clarify, invoke, handoff, normalize |
| [`app/ai/orchestration/graph/builder.py`](../app/ai/orchestration/graph/builder.py) | StateGraph compile |
| [`app/ai/orchestration/graph/run.py`](../app/ai/orchestration/graph/run.py) | `run_assistant_orchestration` → `OrchestratorResult` |
| [`app/ai/orchestration/handoffs.py`](../app/ai/orchestration/handoffs.py) | empty allowlist |

### Information present during one request

| Source | Fields available in-process |
|--------|-----------------------------|
| HTTP | `message` (1–4000 chars); authenticated `User` |
| `AIExecutionContext` | `user_id`, `role_names`, `permission_names`, `employee_id?`, `candidate_id?` (JWT/DB only; frozen) |
| Graph | `available`, `available_ids`, `route_kind`, `route_reason`, `agent_id`, `status`, `answer`, `citations`, `pending_confirmation`, `model`, `tool_names_called`, `usage`, `node_path`, `llm_clarify_attempted`, handoff placeholders |
| Specialist | Domain answer + optional tools/confirm (inside agent; tools never on the graph) |

**Not present today:** `conversation_id`, `message_id`, `request_id`, `execution_id`, persisted history.

Deterministic `route_message` was **not** removed by LangGraph; it is the `select_agent` node.

---

## 2. Current AI response contract

### `POST /api/v1/ai/assistant/ask`

**Request** ([`ai_assistant.py`](../app/api/v1/ai_assistant.py)): `{ "message": string }` only (`extra=forbid`).

**Response `AssistantAskResponse`:**

| Field | Notes |
|-------|--------|
| `agent_id` | Specialist id or `null` (clarify / unavailable) |
| `answer` | User-visible text |
| `citations` | Knowledge RAG refs only in unified envelope |
| `pending_confirmation` | `{ token, tool_name, summary, expires_at }` or null |
| `status` | `completed` \| `clarification_required` \| `unavailable` |
| `model` | Optional |
| `tool_names_called` | High-level names |
| `usage` | Optional token counts |

Hard failures map to HTTP 422 / 403 / 502 (specialist exceptions). Soft outcomes are `200` with clarify/unavailable text.

### Metadata useful for chat history (already available)

- User message text  
- `answer`, `agent_id`, `status`, `citations` (safe subset)  
- `tool_names_called`, `model`, `usage`  
- From graph (not yet in HTTP): `route_reason`, `node_path`  
- Pending: `tool_name`, `summary`, `expires_at` — **not** the raw `token` for long-term storage  

### Identifiers that do **not** exist yet

No server `conversation_id`, `message_id`, or `execution_id` on ask/confirm responses.

### Standalone vs unified

Documents standalone ask can return `document_summary` / `document_answer` (with page excerpts). Those fields are **dropped** on the unified gateway. Document AI panel stays out of unified history MVP.

---

## 3. Specialist agents — what to persist

| Agent | User-visible | Structured extras | Tools / confirm | Must not dump into history |
|-------|--------------|-------------------|-----------------|----------------------------|
| Knowledge | `answer` | RAG `citations` (metadata) | No tools / no confirm | Chunk text, embeddings, full RAG context |
| Leave | `answer` | — | tools + pending | Tool args (employee_id, dates), balance dumps beyond answer |
| Recruitment | `answer` | — | tools + pending | CV text, fit internals, storage keys |
| Onboarding | `answer` | — | tools + pending | Raw task/service payloads |
| Training | `answer` | — | tools + pending | Raw assignment payloads |
| Documents | `answer` (+ panel: summary/Q&A) | page citations with **excerpts** | reads only | Excerpts, private/employee PDF bodies, storage keys |
| Offboarding | `answer` | — | tools + pending | Clearance notes dumps, exit feedback beyond answer |

### Classification

| Class | Persist in chat history? | Examples |
|-------|--------------------------|----------|
| **A. User-visible content** | Yes | User `message`; assistant `answer`; Knowledge citation refs (doc name, pages, `company_document_id`, `citation_id`) |
| **B. Safe metadata** | Yes | `agent_id`, `status`, `route_reason`, `node_path`, `tool_names_called`, `model`, `usage`, pending digest / summary / expiry / resolved |
| **C. Transient execution** | No | Full `OrchestratorState`, LLM turn arrays, tool JSON results, RAG selected chunks |
| **D. Forbidden** | Never | Raw confirmation token; storage keys; presigned URLs; auth secrets; raw tool arguments; CV/document body; private-doc excerpts; RAG context blobs |

**Rule:** “User was allowed to see it once in the UI” ≠ “store forever.” Prefer the **answer text** the model already produced over re-storing tool/RAG payloads.

---

## 4. Tool execution vs chat history

### Today

- Tools run inside specialists via `ToolExecutor` + `authorize_tool`.  
- Writes stop at HMAC propose when `may_require_confirmation` and not `execute_writes`.  
- Token payload includes **full write arguments** (decodable from token) — see [`confirmation/tokens.py`](../app/ai/confirmation/tokens.py).  
- [`ai_tool_action_audits`](../app/ai/audit/models.py): `actor_user_id`, `tool_name`, `phase`, `target_*`, **`arguments_digest` only**, `success`, `error_code`. No raw args, no tokens, no usage.

### Recommendations

| Question | Answer |
|----------|--------|
| Persist tool calls in chat? | **Names only** (`tool_names_called` JSON list) |
| Persist tool arguments? | **No** |
| Persist tool results? | **No** (answer text is enough) |
| Persist confirmation tokens? | **Never** (use SHA-256 digest of token for correlation) |
| Authoritative write audit? | **`ai_tool_action_audits` remains authoritative** |

### Separation

```text
Chat History          → UX continuity (what was said / which agent / soft status)
AI Action Audit       → compliance trail for write propose/confirm/execute
LangGraph runtime     → ephemeral orchestration for one HTTP request
```

Do **not** duplicate audit rows inside chat tables. Confirm success/fail may update `pending_resolved` on a history message (digest match) without writing args.

---

# SECURITY DECISIONS

## 5. Data classification (assistant surface)

| Data | Persist? |
|------|----------|
| User question / assistant answer | Yes (retention-policy subject) |
| Leave / onboarding / training / offboarding facts **as stated in answer** | Yes (answer only) |
| Knowledge citation metadata | Yes |
| Document / CV **excerpts or bodies** | **No** by default |
| Private / employee document content | **No** |
| Candidate / recruitment CV content | **No** |
| RAG retrieval context | **No** |
| Tool args (ids, dates, notes) | **No** |
| Confirmation tokens | **No** |
| Presigned URLs / storage keys | **No** |
| Auth / JWT / secrets | **No** |
| Raw LLM system prompts / full provider payloads | **No** |

---

## 6. Conversation ownership / IDOR

### Identity facts

- Auth principal is always `User.id` (`AIExecutionContext.user_id`).  
- `employee_id` / `candidate_id` are optional profiles.  
- Notifications and AI audits key off **user_id**.

### Locked ownership model

- **Owner = `user_id`** (integer FK → `users.id`).  
- Every list/get/append: `conversation.user_id == current_user.id`.  
- **No HR/Admin cross-user chat access in MVP** (avoids accidental leakage of another user’s assistant thread).  
- Optional nullable `employee_id` / `candidate_id` snapshots at conversation create for analytics — **not** ACL.  
- User A must never read or append to User B’s conversation.  
- Deactivated users: same as rest of API — unauthenticated / inactive users cannot call history endpoints.

**Do not own by `employee_id` alone** (nullable; SET NULL on user unlink; candidates/HR without employee cannot own threads).

---

## 11. Retention / deletion (PFE-minimal)

| Topic | Decision |
|-------|----------|
| Soft delete | **Not required** now (codebase rarely uses `deleted_at`) |
| Delete conversation | Hard delete; **CASCADE** messages |
| Delete single message | Optional later; not required for MVP |
| Automatic retention job | **Not required** for PFE MVP |
| Product note | Answers may contain PII; document that history is user-private and deletable |

---

## 14. Security test plan

### MUST HAVE

- User A cannot GET User B’s conversation or messages  
- User A cannot POST into User B’s `conversation_id`  
- Invalid / unknown `conversation_id` → 404 (not 403 with existence leak preference: 404 for both missing and foreign)  
- Deleted conversation inaccessible  
- Deactivated / unauthenticated user blocked  
- DB fixtures assert **no** raw confirmation token column/value  
- Fixtures / serializers never store `storage_key`, presigned URL patterns, or document excerpts in `citations_json`  
- Message `sequence` ordering stable  
- Conversation created only for authenticated `user_id` (not spoofable body field)  
- Confirm resolve updates `pending_resolved` for matching digest owned by user; foreign digest ignored  

### NICE TO HAVE

- Concurrent appends / sequence uniqueness under load  
- Role change mid-conversation (history still owned by user_id; new asks use new context)  
- Cross-agent contamination (history is display-only; next ask still re-routes)  
- Retention job (if added later)  
- Archived company doc content does not appear in stored citations beyond allowed metadata  

---

# PROPOSED STATE

## 7. Conversation model (minimal)

Supersedes Orc.4 UUID sketch: use **integer PKs** to match `users`, `notifications`, `ai_tool_action_audits`.

### `ai_conversations`

| Column | Type | Notes |
|--------|------|--------|
| `id` | int PK | `conversation_id` |
| `user_id` | int FK → `users.id` ON DELETE CASCADE | Ownership |
| `employee_id` | int NULL | Snapshot only |
| `candidate_id` | int NULL | Snapshot only |
| `title` | varchar NULL | Optional; default = truncated first user message |
| `created_at` / `updated_at` | timestamptz | UTC |

**Index:** `(user_id, updated_at DESC)`.

### `ai_conversation_messages`

| Column | Type | Notes |
|--------|------|--------|
| `id` | int PK | `message_id` |
| `conversation_id` | int FK CASCADE | |
| `role` | enum/string | `user` \| `assistant` only in MVP (no tool/system rows) |
| `content` | text | User text / assistant answer |
| `sequence` | int | Monotonic per conversation (ordering) |
| `agent_id` | varchar NULL | On assistant rows when applicable |
| `status` | varchar NULL | `completed` / `clarification_required` / `unavailable` / `error` |
| `route_reason` | varchar NULL | |
| `node_path` | JSON NULL | Graph node names |
| `tool_names_called` | JSON NULL | String list |
| `citations_json` | JSON NULL | Safe Knowledge refs only |
| `pending_tool_name` | varchar NULL | |
| `pending_summary` | text NULL | |
| `pending_expires_at` | int NULL | Unix expiry |
| `pending_token_digest` | varchar(64) NULL | SHA-256 of token; **not** token |
| `pending_resolved` | bool NULL | null / true / false |
| `model` | varchar NULL | |
| `usage_json` | JSON NULL | |
| `created_at` | timestamptz | |

**Indexes:** `(conversation_id, sequence)` UNIQUE; `(conversation_id, created_at)`.

### Explicit non-goals (MVP)

- No `ai_conversation_tool_calls` table  
- No storing full LangGraph state  
- No soft-delete columns  
- No HR shared inbox of employee chats  

---

## 8. Persistence semantics

| Case | Persist |
|------|---------|
| **A** Success (`completed`) | User message + assistant message |
| **B** Clarification | User + assistant (`status=clarification_required`, `agent_id=null`) |
| **C** Pending confirmation | User + assistant; pending digest/summary/expiry; **no token**; `status=completed` (matches today’s envelope) |
| **D** Confirm succeeds | Update originating assistant row `pending_resolved=true` (digest + user scope). Optional short system-less assistant note **not** required |
| **E** Confirm fails | `pending_resolved=false` or leave unresolved; do not invent success text |
| **F** Soft tool failure inside agent | Persist final `answer` as returned; tool names if any |
| **G** LLM / agent hard fail (HTTP 5xx/422) | Persist user message + assistant stub `status=error`, short safe error content (no stack traces) |
| **H** No available agents / unavailable | User + assistant (`unavailable`) |
| **I** Page refresh | Load conversation by id; show history; Confirm card **not** restored (token absent) |
| **J** Timeout / client abort | Best-effort: if response never committed, no assistant row (or error stub if server finished) |

**Chat history does not resume HMAC confirmation.** User must Confirm in the same browser session with a live token, or re-ask to propose again.

Write timing: after successful normalize / HTTP mapping of soft outcomes; on hard errors after deciding the error stub; confirm endpoints update digest rows without inserting tool audit into chat.

---

## 9. Conversation resumption (FE later)

| Identifier | Needed? | Why |
|------------|---------|-----|
| `conversation_id` | **Yes** | Load/append thread |
| `message_id` | **Yes** (assistant) | Client keys, confirm-resolution correlation |
| `request_id` / `execution_id` | **No** for MVP | No tracing requirement in PFE scope |

Ask request later: optional `conversation_id` (null → create).  
Ask response later: add `conversation_id`, `message_id` (assistant) without removing existing fields.

---

## 10. LangGraph state vs database history

| Layer | Role | Persist? |
|-------|------|----------|
| **A. LangGraph runtime** | One-request orchestration | No (memory only) |
| **B. Chat history DB** | User/assistant turns + safe metadata | Yes (minimal columns above) |
| **C. AI action audit** | Write propose/confirm/execute digests | Yes (existing table only) |

**Do not** dump `OrchestratorState`, specialist internal tool results, or LLM message lists into PostgreSQL.

Minimum from graph worth copying into message metadata: `route_reason`, `node_path`, `agent_id`, `status`, `tool_names_called`, `model`, `usage`, safe citations, pending digest fields.

---

## 12. Database / migration (later)

| Convention | Match |
|------------|--------|
| Head today | `053_offboarding_exit_interview` |
| Next revision | `054_ai_chat_history` |
| PK style | Integer autoincrement |
| Timestamps | timezone-aware UTC |
| Pattern | SQLAlchemy models + repository + thin service; ownership filters like notifications |

Do **not** create the migration in this audit phase.

---

## 13. Frontend impact (later; no changes now)

### Today

[`useAIAssistant.tsx`](../../frontend/src/hooks/useAIAssistant.tsx) / [`types/ai.ts`](../../frontend/src/types/ai.ts): in-memory messages; client ids; stores `agentId`, citations, **live** `pendingConfirmation.token` for Confirm; discards `usage` / `tool_names_called` / `status` for display.

DocumentAIPanel: standalone `/ai/documents/ask` — **out of unified history MVP**.

### Minimal future FE changes

1. Create or accept `conversation_id` (localStorage or server-created on first ask).  
2. Pass `conversation_id` on ask; store returned ids.  
3. On open: `GET` conversation messages → hydrate UI.  
4. Render historical `answer` + citations; show “write was proposed” from summary if unresolved — **without** a Confirm button unless a live token exists in session.  
5. Keep domain confirm routes and `agentId` routing.  

---

# IMPLEMENTATION PLAN (later phase)

## 15. Final architecture recommendation

### A. Minimal database model

`ai_conversations` + `ai_conversation_messages` as in §7 (integer PKs).

### B. Ownership model

`user_id` only for ACL; optional employee/candidate snapshots.

### C. Message model

`user` / `assistant` roles; sequence; safe metadata; pending digest fields; no tool child table.

### D. Persistence lifecycle

§8 — persist after ask soft/hard outcomes; confirm only flips `pending_resolved`.

### E. What is persisted

User text, assistant answer, safe citations, routing/status/tool-name/model/usage metadata, pending digest/summary/expiry/resolved.

### F. What is NOT persisted

Raw tokens, tool args/results, RAG context, document/CV bodies/excerpts, storage keys, presigned URLs, full graph/LLM dumps; Documents panel threads (MVP).

### G. Relationship

```text
LangGraph  = ephemeral request orchestration
Chat DB    = durable UX transcript (user-owned)
Audit DB   = durable write compliance (ai_tool_action_audits)
```

### H. Required backend files (implementation phase)

- `app/ai/history/` (or `app/modules/ai_chat/`) — models, repository, service, schemas  
- API routes: list conversations, get messages, delete conversation; extend ask with optional `conversation_id`  
- Persist hook from `ask_assistant` / `run_assistant_orchestration` result  
- Confirm handlers: resolve pending digest on matching message  

### I. Required frontend files

- `useAIAssistant.tsx`, `types/ai.ts`, `AIComposer` / message list components  
- Optional conversation list UI (can be single active thread MVP)  

### J. Migration

`054_ai_chat_history` after `053_offboarding_exit_interview`.

### K. Required tests

§14 MUST HAVE list.

### L. Security risks

| Risk | Mitigation |
|------|------------|
| IDOR on conversation_id | Always filter by `user_id` |
| Token leakage via history | Never store token; Confirm requires live ask |
| PII in answers | User-owned + hard delete; no cross-user HR browse |
| Tool/RAG dumps | Persist names + answer only |
| Documents excerpts | Keep panel out of history; strip excerpts from any citations_json |

### M. Decisions locked before implementation

1. Owner = `user_id` (not employee_id).  
2. Integer PKs (not UUID).  
3. No raw confirmation tokens in DB.  
4. No tool-arg / tool-result / RAG-context persistence.  
5. No HR cross-user conversation access in MVP.  
6. Confirm not resumable from history after refresh.  
7. `ai_tool_action_audits` remains sole write audit authority.  
8. DocumentAIPanel not in unified history MVP.  
9. Additive API fields only (`conversation_id` / `message_id`); existing FE ask/confirm contract remains valid.  
10. Do not replace LangGraph, `AIExecutionContext`, specialists, or HMAC confirm.

---

## Constraints checklist (this audit)

- [x] No application code changes  
- [x] No migration created  
- [x] No new dependencies  
- [x] No frontend changes  
- [x] Agents / LangGraph / context / HMAC / audits not redesigned  

**End of audit.** Implementation is a separate phase after product acceptance of this document.
