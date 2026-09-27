# Phase 7.3A — Global Agent Access & Authorization Model (Audit)

**Stance:** Audit only. No migrations, permissions, tools, FE, or Leave behavior changes were made in this phase.

**Locked finding:** “Manager” in product terms is primarily **org-chart** (`Employee.manager_id`), not the seeded RBAC role `"manager"`. A user can hold multiple roles (`UserRole`); employee + manager coexistence is schema-supported. AI must separate **agent availability**, **tool capability**, **resource scope**, and **LeaveService business auth**.

---

## A. Current User → Employee model

| Concern | Implementation |
|---------|----------------|
| Authenticated user | `get_current_user` (`backend/app/modules/identity/dependencies.py`) → JWT `sub` → `AuthService.get_user_by_id`; rejects inactive User |
| Roles / permissions | Eager-loaded via `User.user_roles` → `Role` → `Permission`; **not** in JWT; rebuilt every request |
| Employee link | `Employee.user_id` → `users.id` (unique, nullable). **No** `User.employee` ORM back-ref |
| Resolve Employee | Canonical: `EmployeeRepository.get_by_user_id` / `EmployeeService.get_by_user_id` |
| AI context | `build_ai_execution_context` / `get_ai_execution_context`: `user_id`, `role_names`, `permission_names`, `employee_id` (or None), `candidate_id` |
| Active User | `User.is_active` gated at login + `get_current_user` |
| Active Employee | `EmploymentStatus` (ACTIVE/INACTIVE/ON_LEAVE). `get_by_user_id` does **not** filter status — inactive Employee still yields `employee_id` in AI context |

Leave “require employee”: `LeaveService._require_employee_for_user` → 404 if no Employee row.

---

## B. Current Employee → Manager model

| Fact | Detail |
|------|--------|
| Representation | Single optional `Employee.manager_id` self-FK (one manager; many `direct_reports`) |
| Direct reports | `EmployeeRepository.list_direct_report_ids(manager_employee_id)` — **direct only**, no status filter |
| Is A manager of B? | **No** named `is_manager_of`. Equivalent: `B.manager_id == A.id` (used in `classify_actor`) |
| Hierarchy | `EmployeeService.get_hierarchy` builds tree for ACTIVE employees; cycle check in `validate_manager_assignment` |
| Positions | Flat `Position` catalog via `position_id` — **not** a reporting tree |
| Multiple managers | **Not supported** (single column) |
| Recursive reports | **No** subtree / `list_all_report_ids` API |

Leave team inbox: `LeaveService.list_team_requests_for_user` → `list_direct_report_ids` → requests for those IDs.

---

## C. Current RBAC / permission model

| Primitive | Semantics |
|-----------|-----------|
| Seeded roles | `admin`, `hr`, `manager`, `employee`, `candidate` — `SeedService.ROLE_PERMISSIONS` |
| `manager` vs `employee` perms | Essentially **identical** today |
| Multi-role | Allowed. Hire path `_ensure_employee_role` adds `"employee"` only — does **not** auto-assign `"manager"` when `manager_id` is set |
| `require_permissions` | AND over permission names |
| `require_roles` | OR over role names |
| `require_hr_staff` | Role ∈ `{admin, hr}` **then** optional AND permissions |
| AI tools | `authorize_tool`: `required_roles` OR, `required_permissions` AND, optional `operates_on_current_user` |
| Current Leave Agent | Endpoint `require_hr_staff("leaves:read")`; tools require roles `{hr,admin}` + `leaves:read` |
| Self leave tool | `GetMyLeaveBalanceTool`: `leaves:read` + `operates_on_current_user=True` |

**Critical:** Org-chart managers with only `employee`/`manager` roles **cannot** use today’s Leave Agent (HR-staff gated), even though Core Leave team/approve APIs work for them.

---

## D. Current Leave authorization model

| Action | Who | Mechanism |
|--------|-----|-----------|
| Create | Self only | `POST /me/leave/requests` → `create_request_for_user` |
| List all | HR staff | `require_hr_staff` + `list_requests_for_hr` |
| List mine | Self | `list_requests_for_user` |
| List team | Any user with reports | `list_team_requests_for_user` (direct reports; **no** `"manager"` role required) |
| Get by id (HR path) | Admin **or** HR staff **or** `can_user_review_request` | Soft 404 otherwise |
| Approve / reject | Admin / direct manager / HR role | `classify_actor` + `resolve_requirements` at **call time** |
| Manager scope | Direct only | `employee.manager_id == reviewer_employee.id` |
| Cancel pending | Owner | `cancel_request_for_user` |
| Request cancel approved | Owner + future start | `request_cancellation_for_user` |
| Process cancellation | Any non-null `classify_actor` | Broader than staged approve |

Business finalization still re-checks overlap/balance via `_assert_can_finalize_approval` (not RBAC).

---

## E. Reusable authorization primitives (for AI)

| File | Symbol | Purpose |
|------|--------|---------|
| `identity/dependencies.py` | `get_current_user`, `require_permissions`, `require_roles` | Auth + coarse HTTP gates |
| `identity/hr_access.py` | `require_hr_staff` | HR/Admin staff gate |
| `ai/core/context/dependencies.py` | `get_ai_execution_context`, `build_ai_execution_context` | AI identity pack |
| `ai/core/context/models.py` | `AIExecutionContext.has_any_role` | Role OR check (no `has_permission` helper) |
| `ai/tools/authorization.py` | `authorize_tool` | Tool-layer gate |
| `employees/repository.py` | `get_by_user_id`, `list_direct_report_ids` | User→Employee; manager→reports |
| `employees/service.py` | `validate_manager_assignment` | Assign-time manager rules |
| `leave/service.py` | `_require_employee_for_user`, `get_balances` / `get_balances_for_user`, `list_requests_for_user` / `get_request_for_user`, `list_team_requests_for_user`, `list_requests_for_hr` / `get_request_for_hr`, `can_user_review_request`, `approve_request` / `reject_request`, cancellation methods | Leave scope + business auth |
| `leave/approval.py` | `classify_actor`, `resolve_requirements` | Actor class + stage availability |
| `ai/tools/leave.py` | `GetMyLeaveBalanceTool` | Pattern for self-scoped tool |

**Not present** as named helpers: `get_current_employee`, `get_employee_manager`, `is_manager_of`, `can_access_employee`, `can_approve_leave` (use `classify_actor` / `can_user_review_request` instead).

---

## F. Missing capabilities / gaps

1. No unified AI Leave Agent for employee/manager — today’s agent is HR-staff-only.
2. No shared `is_manager_of` / `can_access_employee` helper.
3. No subtree reports — only direct reports.
4. RBAC `"manager"` unused for leave authority — org-chart is authoritative.
5. HR read tools are org-wide — unsafe if exposed to non-HR without scope wrappers.
6. Inactive Employee still linked in AI context.
7. GET single request asymmetry for managers (team list vs review-gated get-by-id).
8. Cancellation process auth broader than approve.
9. No Leave write tools / confirmation path yet.
10. Org viewer quirk — `_require_org_viewer` omits `"manager"` alone.

---

## G. Proposed minimal AI authorization architecture

```
User → Agent availability → Tool capability → Resource scope → Business Service → DB
```

| Layer | Rule | Reuse |
|-------|------|-------|
| **Agent availability** | Who may call which agent endpoint | Decide in 7.3B; today Leave is HR-only |
| **Capability** | Tool metadata permissions/roles / `operates_on_current_user` | `authorize_tool` |
| **Resource scope** | Self → context `employee_id`; manager → `list_team_requests_for_user` / direct reports; HR → `*_for_hr` + HR roles | Never trust LLM foreign IDs without scope check |
| **Business authorization** | Writes call `approve_request` / etc.; service re-runs `classify_actor` + `resolve_requirements` | Service remains authoritative |

Same user as employee + manager: one `AIExecutionContext`; register both self-scoped and team-scoped tools; each tool enforces its own scope.

---

## H. Files for implementation phase (7.3B+) — not modified in 7.3A

- `backend/app/api/v1/ai_leave.py`
- `backend/app/ai/agents/leave/agent.py`, `prompts.py`
- `backend/app/ai/tools/leave_reads.py` / new self/manager tool modules
- `backend/app/ai/tools/leave.py`
- Possibly thin facades on `leave/service.py` (prefer composing existing methods)
- `frontend/src/hooks/useAIAssistant.tsx` (if employee/manager portals get Leave Agent)
- Tests under `backend/app/tests/`

No new tables, permissions, or manager FKs required for this model.

---

## I. Risks / ambiguities

1. One Leave Agent with audience-scoped tools vs separate HR / Manager / Employee endpoints.
2. Prefer org-chart checks over RBAC `"manager"` role as a gate.
3. Inactive / ON_LEAVE managers — already in `resolve_requirements`; AI must not invent overrides.
4. Multi-hat users (HR + manager) — `classify_actor` order: Admin → Manager → HR.
5. Manager “show B’s request” may need team list / ownership checks, not only `get_request_for_hr`.
6. FE today — Leave Agent only on `/hr/leave*`.

---

## J. Recommendation for Phase 7.3B

1. Keep Core `LeaveService` as sole business authority for approve/reject/cancel.
2. Introduce scoped Leave **read** tools before writes: self (`*_for_user`), manager (`list_team_requests_for_user`), HR (keep `*_for_hr` + HR roles).
3. Widen Leave Agent availability to authenticated users with `leaves:read` (and employee link where needed), while capability + scope still block cross-tenant access.
4. Add write tools only after scoped reads work, with Recruitment-style confirmation and service-layer approve/reject.
5. Do **not** create new manager relationship models or new RBAC permissions for “is manager.”

### Manager scenario (current behavior)

**A manages B; B has PENDING leave.**

| Step | Via Core Leave APIs | Via today’s Leave Agent |
|------|---------------------|-------------------------|
| A: “Show B’s pending” | `list_team_requests_for_user` works; get-by-id if `can_user_review_request` | **Blocked** — A is not HR staff |
| A: “Approve it” | `approve_request` → `classify_actor=MANAGER` if direct + stage rules | **No write tool** |
| C (unrelated): “Approve B” | `classify_actor` → `None` → 403 | **Blocked** at agent/tool auth |

Domain already supports A and denies C for approval; **AI Leave surface does not expose manager scope yet.**
