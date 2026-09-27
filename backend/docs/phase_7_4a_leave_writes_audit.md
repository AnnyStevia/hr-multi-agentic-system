# Phase 7.4A — Leave Write Actions Audit

**Stance:** Audit only. No tools, migrations, FE, or LeaveService changes were made in this phase.

**Locked architecture for 7.4B:** Leave Agent → Tool (confirmation-gated) → existing `LeaveService` → DB. Do not reimplement balance/overlap/actor rules in AI code.

---

## 1. Existing Leave write architecture

```
/me/leave/*  ──┐
               ├──→ LeaveService → approval.classify_actor / resolve_requirements
/leave/requests/*/approve|reject|cancellation ──┘
                         ↓
                   LeaveRepository + NotificationService
```

Balances are **derived** (sums of `requested_days` by status), not a separate ledger. Overlap uses inclusive calendar days against PENDING+APPROVED.

Primary sources: `backend/app/modules/leave/service.py`, `approval.py`, `api/v1/leave.py`, `tests/integration/test_leave.py`.

---

## 2. Exact reusable service methods

### Create — SELF only

| Field | Detail |
|-------|--------|
| **A** | `create_request_for_user(user_id, payload)` → `_create_request` |
| **B** | `LeaveRequestCreateRequest`: `leave_type_id`, `start_date`, `end_date`, `reason?` |
| **C–E** | Own employee via `_require_employee_for_user`; cannot create for others |
| **F–G** | New → `PENDING` |
| **H** | Policy required; headroom = `allowed − APPROVED − PENDING` |
| **I** | `end≥start`, same year, active type, no overlap with PENDING/APPROVED |
| **J–K** | No manager/HR role needed to submit |
| **L** | `LEAVE_REQUEST_SUBMITTED` to available manager + available HR (if not HR requester) |
| **M** | Single `add_request` commit |
| **N** | `test_leave.py` validation / flow tests |

### Approve — MANAGER / HR / ADMIN

| Field | Detail |
|-------|--------|
| **A** | `approve_request(request_id, reviewer_user_id)` |
| **J** | **Yes:** `employee.manager_id == reviewer_employee.id` in `classify_actor`; self forbidden |
| **K** | HR / Admin via classify; dual-approval + availability via `resolve_requirements` |
| **H–I** | Rechecked **only on finalize** via `_assert_can_finalize_approval` |
| **L** | Final: `LEAVE_REQUEST_APPROVED`; partial manager: notify HR |

### Reject — MANAGER / HR / ADMIN

| Field | Detail |
|-------|--------|
| **A** | `reject_request(request_id, reviewer_user_id, rejection_reason)` |
| **F–G** | `PENDING` → `REJECTED` |
| **J–K** | Same `classify_actor` + stage gates as approve |

### Cancel pending — SELF

| Field | Detail |
|-------|--------|
| **A** | `cancel_request_for_user(user_id, request_id)` |
| **F–G** | `PENDING` → `CANCELLED` |
| **E** | Owner only |

### Request cancel approved — SELF

| Field | Detail |
|-------|--------|
| **A** | `request_cancellation_for_user(user_id, request_id, reason)` |
| **F–G** | Stays APPROVED; `cancellation_status=REQUESTED`; requires `start_date > today` |

### Approve / reject cancellation — MANAGER / HR / ADMIN

| Field | Detail |
|-------|--------|
| **A** | `approve_cancellation` / `reject_cancellation` |
| **J–K** | Any non-null `classify_actor` (broader than leave approve — no dual-stage wait) |

**HTTP pattern:** Review routes use `get_current_user` only; service enforces actor.

---

## 3. Existing authorization guarantees

- Manager authority = org chart (`manager_id`), not RBAC `"manager"`.
- Admin can finalize/override; HR follows dual-approval + availability.
- Self cannot approve/reject own leave or process own cancellation.
- Create / pending cancel / request cancel are owner-scoped only.
- Cancellation processing is wider than leave approve — AI must call these methods as-is.

---

## 4. Existing confirmation / audit infrastructure (reuse)

**Shared (reuse for Leave writes):**

| Component | Path | Role |
|-----------|------|------|
| HMAC tokens | `ai/confirmation/tokens.py` | Bind user + tool + canonical args + exp |
| Executor gate | `ai/tools/executor.py` | `may_require_confirmation` when `execute_writes=False` |
| Authz | `ai/tools/authorization.py` | Re-run on confirm |
| Audit | `ai/audit/` | proposed → confirmed → executed/failed |
| Roundtrip | `ai/orchestration/tool_roundtrip.py` | Pending hint to LLM |

**Recruitment-specific (copy pattern):** `RecruitmentAgent.confirm`, `POST /ai/recruitment/confirm`, `_infer_target`, FE confirm UX.

**Replay:** No `jti` burn; rely on LeaveService state machines (same as recruitment).

---

## 5. Proposed Leave write tools (for 7.4B)

All: `operation=write`, `may_require_confirmation=True`, `leaves:write`, wrap service only.

| Tool | Scope | Service |
|------|-------|---------|
| `create_leave_request` | SELF | `create_request_for_user` |
| `approve_leave_request` | MANAGER/HR/ADMIN via service | `approve_request` |
| `reject_leave_request` | same | `reject_request` |
| `cancel_pending_leave_request` | SELF | `cancel_request_for_user` |
| `request_leave_cancellation` | SELF | `request_cancellation_for_user` |
| `approve_leave_cancellation` | MANAGER/HR/ADMIN | `approve_cancellation` |
| `reject_leave_cancellation` | MANAGER/HR/ADMIN | `reject_cancellation` |

Do **not** implement create-on-behalf. Confirm endpoint needs `leaves:write`. Extend `_infer_target` for `request_id` → leave_request.

---

## 6. Risks / edge cases

1. Dual-approval partial approve — do not claim fully approved until tool result says so.
2. Cancellation process auth broader than leave approve.
3. Concurrent finalize race (no row lock) — same as Core UI.
4. Display `days_available` vs create headroom.
5. HR without employee profile can review but cannot create self leave.
6. FE confirm UI is recruitment-only today.
7. API 502 must stay generic on confirm failures.

---

## 7. Exact implementation files for Phase 7.4B

**Create:** `backend/app/ai/tools/leave_writes.py`; unit/integration confirm tests.

**Modify:** `leave/agent.py`, `schemas.py`, `prompts.py`, `api/v1/ai_leave.py`, `tools/executor.py` (`_infer_target`), `tools/__init__.py`; FE confirm wiring only if required for leave paths.

**Do not modify:** LeaveService business rules, migrations, manager model, unrelated domains.
