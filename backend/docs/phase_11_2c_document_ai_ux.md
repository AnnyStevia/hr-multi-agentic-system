# Phase 11.2C — Document AI UX + Upload Integration

**Stance:** End-to-end Document AI experience on already-uploaded documents. Upload remains Core HR. AI operates via the standalone Documents Agent (`POST /api/v1/ai/documents/ask`). **No** AI upload tool, **no** unified registry/router changes, **no** write/confirm tools, **no** migration.

Alembic head remains **`048_employee_training_progress`**.

---

## Architecture

```text
Frontend document UI
  ├── normal upload → DocumentService / library services → StorageService → S3
  └── DocumentAIPanel
        → POST /api/v1/ai/documents/ask  (document_id + document_type in message only)
        → DocumentsAgent
        → summarize_document / ask_about_document
        → DocumentUnderstandingService
        → StorageService → PDF bytes
```

**Why no AI upload:** File intake stays a normal Core HR/document operation (validation, quotas, ownership, virus/size checks). The agent must never receive base64 bytes, storage keys, or presigned URLs. Users explicitly choose “Summarize with AI” after upload to avoid surprise cost and processing.

---

## Upload integration

- Existing endpoints unchanged (`company-documents`, `me/private-documents`, `me/documents`, `employees/{id}/documents`).
- After a successful **PDF** upload, the list refreshes and the Document AI panel may open for that document.
- The LLM is **not** invoked automatically on upload.

---

## Summary flow

1. User clicks **Summarize with AI** on an eligible PDF.
2. Frontend calls `askDocumentsAgent` with a deterministic message identifying `document_id`, `document_type` (`company` | `employee` | `private`), and optional `employee_id` (HR employee docs only).
3. Agent runs `summarize_document`.
4. HTTP response includes free-text `answer` plus structured `document_summary` (title, summary, key_points, important_dates, action_items) harvested from the tool result.
5. UI renders structured sections; empty lists are hidden.

---

## Q&A flow

1. User asks a question in the panel.
2. Same ask endpoint; message identifies the document again (no conversation-history inference).
3. Agent runs `ask_about_document`.
4. Response includes `document_answer` with page citations (`page_number`, optional short `excerpt`).
5. UI shows answer + `Source: p. N` / `Sources: pp. N, M`. Session-only turns; no persistent document chat.

---

## Authorization (frontend gates + backend authority)

| Source | AI actions shown when | Backend authority |
|--------|----------------------|-------------------|
| Company | ACTIVE + PDF | Understanding requires authorized ACTIVE content access |
| Private | PDF on owner’s list | Owner-only; HR/Admin cannot override |
| Employee | PDF; self or HR view | Self session or HR + `employee_id` |
| Archived company | Metadata only for HR; **no** content AI buttons | Understanding / ACTIVE gate rejects content AI |
| Candidate ApplicationDocument / CV | **No Document AI UI** | Excluded from Document Understanding |

Managers do **not** gain employee-document AI access via management relationships.

Frontend never decides authorization for content access; failed understanding tools are promoted to HTTP **403** / **422** / **502** as appropriate.

---

## Supported PDF scope

- MIME `application/pdf` (filename `.pdf` fallback on the client for action visibility).
- Non-PDF upload/list behavior unchanged; AI buttons hidden.

---

## Structured ask response (11.2C addition)

`DocumentsAskResponse` / `DocumentsAgentAnswer` now optionally include:

- `document_summary`
- `document_answer` (with citations)

Populated from the last successful `summarize_document` / `ask_about_document` `ToolResult.data`. Still a single ask endpoint—no second HTTP architecture.

---

## Explicit non-goals

- No `DOCUMENTS_AGENT` in the unified assistant registry
- No `ai_assistant.py` / routing changes
- No AI write tools (upload/delete/archive/restore/replace)
- No confirmation / HMAC / action-audit migration
- No persistent document chat history

---

## Known limitations

- Panel Q&A is session-only and independent per question.
- Structured fields depend on the agent calling the understanding tools; the UI prefers structured payloads over free-text.
- Document Understanding remains PDF-only and separate from Company Knowledge RAG indexing.
- No dedicated frontend unit test runner in this repo; validation is TypeScript/build + backend tests + manual checklist.

---

## Next phase

Integrate the Documents Agent into the unified assistant registry/router when that phase is scheduled. Do not start that work as part of 11.2C.
