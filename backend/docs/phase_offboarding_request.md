# Phase — Employee Offboarding Request (pre-case)

## Purpose

Lightweight **OffboardingRequest** layer so an employee can tell HR “I want to leave” **before** an Offboarding Case exists.

HR reviews the request (approve / reject). Opening the case remains the existing O.1 `POST /offboarding` flow. O.1 / O.2 case and checklist behaviour is **unchanged**.

## Flow

1. Employee submits request (`POST /api/v1/offboarding/requests`)
2. HR staff receive `offboarding_request_submitted` notifications
3. HR approves (`POST .../approve`) → creates OffboardingCase via existing `create_for_hr` + O.2 seed, links `offboarding_case_id`, returns case detail
4. Employee is notified of the decision
5. HR UI navigates to `/hr/offboarding/{case_id}`
6. O.1 / O.2 checklist workflow continues as before
7. Recovery: `POST .../create-case` for approved-but-unlinked requests; optional `PATCH .../link-case`

## Data model

Table: `offboarding_requests` (module: `app.modules.offboarding_requests`)

| Field | Notes |
|-------|--------|
| `employee_id` | Submitter (from auth → employee profile) |
| `reason` | Reuses `offboarding_reason` enum; employee form allows resignation, end_of_contract, retirement, other only |
| `reason_details` | Optional message |
| `requested_last_working_day` | Intent only; HR may change on case create |
| `status` | `pending` · `approved` · `rejected` · `cancelled` |
| `submitted_at` / `reviewed_*` / `rejection_reason` | Review metadata |
| `offboarding_case_id` | Optional FK after HR creates + links a case |
| `created_at` / `updated_at` | Timestamps |

**Constraint:** at most one `pending` request per employee (partial unique index).

## API

Employee (`get_current_user` + own employee profile):

- `POST /api/v1/offboarding/requests`
- `GET /api/v1/offboarding/requests/me`
- `POST /api/v1/offboarding/requests/{id}/cancel`
- Legacy aliases: `/api/v1/me/offboarding/requests*`

HR (`offboarding:read` / `offboarding:write`):

- `GET /api/v1/offboarding/requests`
- `GET /api/v1/offboarding/requests/{id}`
- `POST /api/v1/offboarding/requests/{id}/approve` → creates case + returns case detail
- `POST /api/v1/offboarding/requests/{id}/reject`
- `POST /api/v1/offboarding/requests/{id}/create-case` → recovery if approved but unlinked
- `PATCH .../approve|reject` (aliases)
- `PATCH /api/v1/offboarding/requests/{id}/link-case`

## Create case from approved request

`POST /api/v1/offboarding/requests/{id}/approve` (HR `offboarding:write`):

- Creates the OffboardingCase via existing `OffboardingService.create_for_hr` (reason / details / last working day from the request)
- Seeds O.2 checklist via normal case creation
- Sets request to `approved` and `offboarding_case_id`
- If case creation fails, request stays `pending`
- Returns the created case detail (`initiated`)

`POST .../create-case` remains as recovery for approved requests that have no linked case.

## Notifications

| Type | Recipients |
|------|------------|
| `offboarding_request_submitted` | HR/admin staff |
| `offboarding_request_approved` | Employee |
| `offboarding_request_rejected` | Employee |

`related_entity_type=offboarding_request`

## Submit rules

- Employee profile required; employment must be **active**
- Requested last working day not in the past
- Rejected if an **active offboarding case** already exists
- Rejected if a **pending** request already exists
- Employee cannot use `termination` as request reason

## Explicit non-goals

- Auto-creating `OffboardingCase` on approve
- Changes to `OffboardingTask` behaviour or case status machine
- Clearance, exit interview, Meet, AI
- New permissions (reuse `offboarding:read` / `offboarding:write`)

## Migration

- `051_offboarding_requests` — table + `offboarding_request_status` + notification enum values

## Frontend

- Employee `/employee/offboarding/request` — submit form + status
- HR `/hr/offboarding/requests` — list + approve/reject
- Case pages keep case/task focus with links to the request pages
- Notification bell → dedicated request pages

## Tests

`backend/app/tests/integration/test_offboarding_requests.py`
