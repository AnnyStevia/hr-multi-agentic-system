# Phase O.6B — Offboarding Agent (READ-ONLY)

Standalone read-only Offboarding Agent wrapping `OffboardingService` (and HR employee search via `EmployeeService`).

## Endpoint

`POST /api/v1/ai/offboarding/ask` with `{ "message": "..." }`.

Response: `agent_id=offboarding`, `answer`, `tool_names_called`, `pending_confirmation=null`.

**Unified Assistant (O.6C):** also reachable via `POST /api/v1/ai/assistant/ask` when routed. See [`phase_offboarding_6c_unified.md`](phase_offboarding_6c_unified.md).

**Writes (O.6D):** confirmation-gated complete / clearance / task tools — see [`phase_offboarding_6d_writes.md`](phase_offboarding_6d_writes.md).

## Tools

1. `get_offboarding_case`
2. `get_offboarding_progress`
3. `list_offboarding_tasks`
4. `get_offboarding_clearance`
5. `get_exit_interview`
6. `get_offboarding_readiness`
7. `find_employees_for_offboarding` (HR companion; does not change `find_employees` / `recruitment:read`)

## Auth

- HR/Admin + `offboarding:read`: all tools
- Employee with `employee_id`: self dual-mode tools only
- Managers/candidates: no HR tools; no self without employee profile

## Readiness

Terminal `completed` / `cancelled` → `ready=false`, `terminal=true`, no `can_complete()` call. Otherwise domain `can_complete()`.
