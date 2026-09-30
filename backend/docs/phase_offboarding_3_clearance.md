# Phase O.3 — Offboarding Clearance

## 1. Purpose

Add an **Offboarding Clearance** verification layer on top of the existing Offboarding Case (O.1) and Checklist (O.2).

Clearance records whether company **equipment** and **system access** have been verified as returned / revoked. It is intentionally separate from `OffboardingTask` (work items).

This phase does **not** gate case `complete()`, add notifications, exit interviews, AI, or real IT revocation.

## 2. Entity

Table: `offboarding_clearance_items`

| Field | Type | Notes |
|-------|------|--------|
| `id` | int PK | |
| `offboarding_case_id` | FK → `offboarding_cases` | CASCADE delete |
| `category` | enum | `equipment`, `access` |
| `item` | string(200) | Label (e.g. Laptop) |
| `status` | enum | `pending` (default), `cleared`, `not_applicable` |
| `notes` | text nullable | |
| `completed_at` | timestamptz nullable | Set only when status → `cleared` |
| `completed_by_user_id` | FK → `users` SET NULL | Auth actor when cleared; cleared on reopen / N/A |
| `created_at` / `updated_at` | timestamptz | |

Migration: **`052_offboarding_clearance`** (revises `051_offboarding_requests`).

## 3. Default seed

On `OffboardingService.create_for_hr`, after `_seed_default_tasks`, `_seed_default_clearance` runs in the **same transaction**.

Templates: `DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES` in `templates.py`.

- Equipment: Laptop; Badge / access card; Company phone; Other company equipment
- Access: Email; VPN; GitHub / repositories; Internal applications; Other systems

Idempotent: seed skipped if the case already has clearance rows.

## 4. Progress

- `required = total - not_applicable`
- If `required == 0` → `percentage = 100`, `clearance_complete = true`
- Else `percentage = round(cleared / required * 100)`
- `clearance_complete` iff all required items are `cleared`

Helpers (not wired to `complete()` yet): `is_clearance_complete`, `has_pending_clearance`.

## 5. API

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/offboarding/{case_id}/clearance` | `offboarding:read` |
| GET | `/api/v1/offboarding/{case_id}/clearance/progress` | `offboarding:read` |
| POST | `/api/v1/offboarding/{case_id}/clearance` | `offboarding:write` |
| PATCH | `/api/v1/offboarding/{case_id}/clearance/{item_id}` | `offboarding:write` |
| GET | `/api/v1/me/offboarding/clearance` | authenticated employee (active case only) |

## 6. UI

- HR case detail: **Clearance** section (progress, Equipment/Access groups, Clear / N/A / Reopen, notes, add custom)
- Employee `/employee/offboarding`: read-only Clearance list

## 7. Explicit non-goals

- No change to case lifecycle finalization gating
- No task API/model changes beyond shared create seed
- No request-layer changes, notifications, exit interview, AI, IT revoke
