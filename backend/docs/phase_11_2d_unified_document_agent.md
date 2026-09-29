# Phase 11.2D — Unified Document Agent Integration

**Stance:** Register and route the existing read-only Documents Agent through the unified HR Assistant. Standalone `POST /api/v1/ai/documents/ask` and DocumentAIPanel remain unchanged. **No** confirmation, **no** write tools, **no** migration.

Alembic head remains **`048_employee_training_progress`**.

---

## 1. Registry

`DOCUMENTS_AGENT` is registered alongside Knowledge, Leave, Recruitment, Onboarding, and Training:

| Field | Value |
|-------|--------|
| `id` | `documents` |
| `display_name` | Document Agent |
| `supports_confirmation` | `false` |
| `required_permissions_any` | `company_documents:read` (metadata only; not tool auth) |

---

## 2. Availability

Same shape as Training (not bare permission alone):

| Principal | Documents available? |
|-----------|----------------------|
| Employee (`employee_id` present) | Yes |
| Manager (`employee_id` present) | Yes |
| HR/Admin with `company_documents:read` (even without employee profile) | Yes |
| Candidate | No |
| Bare `company_documents:read` without employee_id and without HR/Admin | No (Knowledge may still be available) |

**Availability ≠ authorization.** Tools and Document Understanding still enforce company ACTIVE content, private owner-only, and employee self/HR access. Managers do not gain HR employee-document lookup through the unified agent.

---

## 3. Routing

Deterministic keyword router only (no LLM supervisor).

Document-scoped preference fires when explicit document-operation markers appear (`summarize`, `this PDF`, `my private documents`, `list company documents`, `training PDF`, `leave policy PDF`, etc.).

Institutional policy questions stay on Knowledge unless those markers are present.

---

## 4. Document vs Knowledge

| Responsibility | Agent |
|----------------|-------|
| Company RAG / policies / handbook Q&A without a specific file op | Knowledge |
| Summarize / ask-about a named or “this” document; library/vault lists | Documents |

Document Agent does **not** run Company RAG. Knowledge does **not** use DocumentUnderstandingService.

---

## 5. Document vs Leave / Training

| Example | Agent |
|---------|-------|
| How many leave days do I have? | Leave |
| What does my leave policy PDF say? | Documents |
| What training do I have? | Training |
| What does my training PDF say? | Documents |

---

## 6. Routing table

| Intent | Agent |
|--------|-------|
| Summarize this PDF / Summarize the employee handbook | Documents |
| What does this document say? / What does this PDF say? | Documents |
| Show my private documents / List company documents | Documents |
| What is our leave / annual leave / remote work policy? | Knowledge |
| How many leave days do I have? | Leave |
| What training do I have? | Training |
| What does my training PDF say? | Documents |
| According to the handbook, how many annual leave days? | Knowledge |

---

## 7. Security boundaries

- Unified routing only selects the agent.
- Document tools / domain services remain authoritative.
- “Show me Ahmed’s private documents” cannot bypass owner-only private access.
- Manager cannot use HR employee-document listing through management relationships.
- No chat-history-based document authorization; each request is independent.
- Missing document identity → agent asks for clarification; no implicit “latest upload.”

---

## 8. Standalone endpoint

`POST /api/v1/ai/documents/ask` continues to work and still returns structured `document_summary` / `document_answer` for DocumentAIPanel.

Unified `POST /api/v1/ai/assistant/ask` returns the standard envelope (`agent_id`, `answer`, …) with `agent_id = "documents"` and **empty** Knowledge-style citations (structured Document Understanding payloads stay on the standalone endpoint).

---

## 9. Frontend

- `AssistantAgentId` includes `"documents"`.
- DocumentAIPanel still calls `askDocumentsAgent` (standalone).
- No confirmDocumentsAction / documents confirm UI (read-only).

---

## 10. No confirmation

`supports_confirmation = false`. No `/ai/documents/confirm`, HMAC, or action audits.

---

## Known limitations

- Unified chat does not render structured summary cards / page citations the way DocumentAIPanel does.
- Router is deterministic keyword-based; ambiguous phrasing may still clarify.
- No persistent document chat; no AI upload/writes.

---

## Next phase (out of scope)

Persistent document chat, AI writes, embeddings/vector DB for personal docs, candidate CV Document Agent merge — not part of 11.2D.
