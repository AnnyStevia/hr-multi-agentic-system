# Phase 11.2B — Document Agent Read-Only

**Stance:** Standalone read-only Document Agent with metadata + Document Understanding tools. **No** unified registry/router/FE, **no** write/confirm tools, **no** migration.

Alembic head remains **`048_employee_training_progress`**.

---

## Architecture

```text
POST /api/v1/ai/documents/ask
  → AIExecutionContext
  → DocumentsAgent
  → ToolExecutor / tool roundtrip
  → document_reads tools
  → CompanyDocumentService / DocumentService / PrivateDocumentService
  → DocumentUnderstandingService (summarize / Q&A)
  → StorageService (only via understanding access layer)
```

Agent never receives PDF bytes, `storage_key`, or presigned URLs.

---

## Available tools (8)

| Tool | Purpose |
|------|---------|
| `list_company_documents` | Company library metadata |
| `get_company_document` | One company doc metadata |
| `list_company_document_categories` | Categories |
| `list_my_private_documents` | Own private vault |
| `list_my_employee_documents` | Own HR/onboarding docs |
| `list_employee_documents_for_hr` | HR peer employee docs |
| `summarize_document` | Structured summary via 11.2A |
| `ask_about_document` | Grounded Q&A + page citations |

No upload/delete/archive/restore/reindex tools.

---

## Authorization matrix

| Tool | Gate |
|------|------|
| Company list/get/categories | `company_documents:read`; non-HR ACTIVE-only metadata; HR may see archived **metadata** |
| Private list | Session `user_id` only (owner) |
| My employee docs | Session `user_id` |
| HR employee docs | HR/Admin + `documents:read` |
| Summarize / ask | Tool gate open; domain/`AuthorizedDocumentAccess` authoritative (ACTIVE company content; private owner; employee self or HR+`employee_id`) |

Managers cannot use HR employee-document lookup.

---

## Summary / Q&A flow

1. Resolve document via list/get if needed  
2. `summarize_document` / `ask_about_document` with `document_id` + `document_type`  
3. Understanding service authorizes, downloads via domain services, parses PDF, calls LLM  
4. Returns structured summary or answer + validated page citations  

**Document Understanding ≠ Company Knowledge RAG:** one selected document vs indexed institutional retrieval.

---

## Boundaries

- Company / employee / private remain separate tables and auth paths  
- Candidate ApplicationDocument / CV excluded  
- Archived company docs: metadata visible to HR via list/get; content understanding still ACTIVE-only (11.1B/11.2A)

---

## Why no S3 in the agent

Tools return compact metadata or understanding results. Bytes stay inside `DocumentUnderstandingService` after domain-authorized download.

---

## Read-only guarantees

- No confirmation endpoint  
- No HMAC  
- `pending_confirmation` always `null`  
- No write tools registered  

---

## HTTP

`POST /api/v1/ai/documents/ask` with `{ "message": "..." }`  
Response: `answer`, `agent_id: "documents"`, `tool_names_called`, `model`, `usage`, `pending_confirmation: null`

Not registered in unified assistant.

---

## Known limitations

- No unified routing yet  
- No FE  
- PDF-only understanding  
- Policy questions without a document should clarify / use Knowledge Agent later  
- Optional `employee_id` only for HR employee-type understanding  

---

## Next phase

Auth hardening / confirmation-gated writes / FE confirm / registry + unified assistant (later).

---

## Validation (this phase)

| Suite | Result |
|-------|--------|
| Document Agent unit | **20 passed** |
| Document Understanding + Agent | **42 passed** |
| Docs/RAG/company regression | **70 passed** |
| Peer agent sample | **53 passed** |
| Smoke `smoke_document_agent.py` | **OK** (mocked) |
| Alembic heads | **`048_employee_training_progress`** (no migration) |
| Frontend | Untouched |
| Registry / routing / `ai_assistant.py` | Untouched |
