# Phase O.1 — Offboarding Case Foundation

## 1. Purpose

Introduce the **Offboarding Case** as a first-class Core HR domain: create, list, view, and transition cases with an explicit server-side lifecycle.

This phase is intentionally **case-only**. It establishes the aggregate later phases will attach checklist, clearance, exit interview, and an AI Offboarding Agent to — without redesigning the core.

## 2. Entity

Table: `offboarding_cases`

| Field | Type | Notes |
|-------|------|--------|
| `id` | int PK | |
| `employee_id` | FK → `employees.id` RESTRICT | No duplicated employee fields |
| `reason` | enum | Controlled taxonomy |
| `reason_details` | text nullable | Optional free text |
| `last_working_day` | **date** | Calendar day, not timestamp |
| `status` | enum | Small lifecycle |
| `initiated_at` | timestamptz | Set on create |
| `completed_at` | timestamptz nullable | Set on complete |
| `created_by_user_id` | FK → `users.id` SET NULL | HR actor |
| `created_at` / `updated_at` | timestamptz | Standard audit |

Module: `backend/app/modules/offboarding/` (`models`, `schemas`, `repository`, `service`, `dependencies`).

## 3. Reason enum

Stored snake_case values:

- `resignation`
- `end_of_contract`
- `termination`
- `retirement`
- `other`

## 4. Lifecycle

Statuses:

- `initiated`
- `in_progress`
- `pending_clearance`
- `completed` (terminal)
- `cancelled` (terminal)

Allowed transitions (service methods; **no** arbitrary status PATCH):

```
initiated → in_progress | cancelled
in_progress → pending_clearance | cancelled
pending_clearance → completed | in_progress | cancelled
```

API actions:

- `POST /api/v1/offboarding/{id}/start`
- `POST /api/v1/offboarding/{id}/pending-clearance`
- `POST /api/v1/offboarding/{id}/complete`
- `POST /api/v1/offboarding/{id}/cancel`

Invalid transitions → `400`. Missing case → `404`.

## 5. Authorization

Permissions (seeded): `offboarding:read`, `offboarding:write` — **admin + hr only**.

| Actor | Create / list / detail / transition / cancel | Self view (`GET /me/offboarding`) |
|-------|-----------------------------------------------|-----------------------------------|
| Admin / HR | Yes (`require_hr_staff`) | N/A (use HR APIs) |
| Employee | No | Own cases only (session identity) |
| Manager | No general offboarding authority | Only if they have an employee record (own cases) |
| Candidate | No | No |

Employee-safe fields: `status`, `reason`, `last_working_day`, `initiated_at`, `completed_at` (no `reason_details` / `created_by`).

## 6. Duplicate protection

**Active** = `initiated` | `in_progress` | `pending_clearance`.

- Service: reject create with **409** if an active case exists for the employee.
- PostgreSQL partial unique index `uq_offboarding_cases_one_active_per_employee` on `employee_id` where status is one of the three active values (defense in depth). SQLite tests rely on the service check.

Historical `completed` / `cancelled` cases are retained; a new case may be created after them.

## 7. Employee self-access

`GET /api/v1/me/offboarding` resolves the employee from the authenticated user. No client-supplied `employee_id` / `user_id`. Employees cannot create, transition, cancel, or access HR endpoints.

## 8. Completion behavior (temporary O.1 rule)

`complete` only requires:

1. HR/Admin + `offboarding:write`
2. Current status = `pending_clearance`

It does **not** verify checklist, clearance, exit interview, access revocation, or equipment return. Those prerequisites belong to later phases.

Creating or completing a case does **not** deactivate the User or Employee.

## 9. Intentionally deferred

- Offboarding checklist
- Clearance items
- Exit interview (+ Google Meet)
- Notifications for offboarding events
- AI / Offboarding Agent / unified assistant integration
- Persistent chat / analytics
- Automatic account deactivation or role revocation

## 10. Future phases

```
Offboarding
  ├── Checklist
  ├── Clearance
  ├── Exit Interview
  └── AI Offboarding Agent
```

## API summary

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/v1/offboarding` | HR write |
| GET | `/api/v1/offboarding` | HR read (`?status=&employee_id=`) |
| GET | `/api/v1/offboarding/{id}` | HR read |
| POST | `/api/v1/offboarding/{id}/start` | HR write |
| POST | `/api/v1/offboarding/{id}/pending-clearance` | HR write |
| POST | `/api/v1/offboarding/{id}/complete` | HR write |
| POST | `/api/v1/offboarding/{id}/cancel` | HR write |
| GET | `/api/v1/me/offboarding` | Authenticated employee |

## Migration

- Revision: `049_offboarding_cases`
- Revises: `048_employee_training_progress`

## Frontend

- HR: `/hr/offboarding` (list + create), `/hr/offboarding/[id]` (detail + lifecycle actions)
- Employee: `/employee/offboarding` (read-only)

## Tests

`backend/app/tests/integration/test_offboarding.py` — create validations, duplicate protection, full lifecycle matrix, auth matrix, self-access / IDOR, employment preservation, no status PATCH.
