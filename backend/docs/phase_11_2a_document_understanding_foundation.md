# Phase 11.2A — Document Understanding Foundation

**Stance:** Reusable AI service layer for summarizing and answering questions about **one** explicitly selected, authorized PDF. **No** Document Agent, tools, AI HTTP routes, registry, router, frontend, or migrations.

Alembic head remains **`048_employee_training_progress`**.

---

## Purpose

Foundation for a future AI Document Assistant:

```text
Upload/select document → AI Summary → Document Q&A → grounded page citations
```

This phase ships only the understanding **service**. Agents and unified assistant integration come later.

---

## Architecture

```text
Caller (future Agent/API)
  → DocumentUnderstandingService
      → AuthorizedDocumentAccess (RBAC before bytes)
          → CompanyDocumentService / DocumentService / PrivateDocumentService
              → StorageService.download_file
      → PdfDocumentParser (reuse) + page/char bounds
      → DocumentContext (untrusted DATA framing)
      → LLMProvider.generate_structured
      → page citation sanitization
```

AI code does **not** access S3 keys directly, repositories, or presigned URLs.

---

## Document Understanding ≠ Company Knowledge RAG

| | Company Knowledge RAG | Document Understanding |
|--|----------------------|------------------------|
| Scope | Indexed institutional library chunks | One selected document |
| Access | Retrieval filters + embeddings | Authorize then download that file |
| Citations | Chunk / document markers from RAG | Page numbers in the current PDF |
| Archived company docs | Ineligible (11.1B) | ACTIVE-only download (404 if archived) |

---

## Supported document types

- **PDF only** (via existing `PdfDocumentParser`)
- Sources: `company`, `employee`, `private`
- **Not supported:** candidate `application` / CV / cover letter (Recruitment Agent)

DOCX and image OCR are out of scope.

---

## Authorization boundaries

| Source | Rule |
|--------|------|
| Company | `company_documents:read`; file load requires **ACTIVE** (archived → 404 even for HR) |
| Private | Owner via authenticated `user_id` only; no HR override |
| Employee (self) | Caller’s `employee_id` / user ownership |
| Employee (other) | HR/Admin **and** `documents:read` + explicit `employee_id` |
| Manager | No employee-document bypass |
| Application | Rejected as unsupported |

Unauthorized / missing → opaque **Document not found** / authorization errors consistent with Core HR.

---

## Summary flow

1. Resolve authorized bytes  
2. Parse + bound pages/characters  
3. `generate_structured` → `DocumentSummary`  
   (`title`, `summary`, `key_points[]`, `important_dates[]`, `action_items[]`)  
4. Empty date/action arrays are valid; do not invent  

No database mutation.

---

## Q&A flow

1. Same authorize + parse path  
2. Structured answer + citations  
3. Grounded only in supplied pages  
4. Abstention: *"I couldn't find enough information in this document to answer that."*

---

## Citation validation

After generation, keep only citations whose `page_number` exists in the **current** parsed document. Invalid pages are dropped. Citation schema has no `storage_key`, company-chunk IDs, or cross-document fields.

---

## Prompt injection handling

- System instructions stay in the system message  
- Document text is framed as untrusted DATA in the user message  
- Injection phrases are treated as content, not commands  
- Responses must not expose system prompts, keys, storage keys, or auth context  

---

## Size / token limits

| Limit | Default |
|-------|---------|
| Upload/download size | 5 MiB (`MAX_DOCUMENT_BYTES`) |
| Max pages to LLM | 40 |
| Max characters to LLM | 30_000 |
| Max output tokens | 800 |
| Temperature | 0.1 |

Truncation is deterministic (pages in order until budget); `truncated=True` is surfaced on results.

No embeddings / second vector DB.

---

## Why Candidate ApplicationDocument is excluded

CV/cover-letter access and extraction remain under Recruitment. Mixing application docs into Document Understanding would blur authorization and product boundaries.

---

## Known limitations

- PDF-only; no DOCX/OCR  
- No HTTP AI endpoints or Document Agent yet  
- Large PDFs are truncated, not chunk-retrieved via vectors  
- Restore/reindex of company library is unrelated (11.1B)  
- Employee HR path requires explicit `employee_id` on the ref  

---

## Next phase

Document Agent (read tools / ask API), then auth hardening, confirmation-gated writes, FE confirm plumbing, and unified assistant registration — **after** this foundation is stable.

---

## Tests

| Coverage | Location |
|----------|----------|
| Auth matrix + parse bounds + summary/Q&A + injection + domain ACTIVE gate | `test_document_understanding.py` |

### Validation (this phase)

| Suite | Result |
|-------|--------|
| Document Understanding unit | **22 passed** |
| Related documents / RAG regression | **60 passed** |
| Broader backend unit suite | **572 passed**, **1 failed** — known pre-existing `test_unauthorized_tool_call_surfaces_as_agent_error` (untouched) |
| Alembic heads | **`048_employee_training_progress`** (no migration) |
| Frontend | Untouched |
| Document Agent / registry / router | Not created |
