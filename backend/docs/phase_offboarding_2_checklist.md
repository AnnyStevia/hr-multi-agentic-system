# Phase O.2 — Offboarding Checklist

## Purpose

Add the **OffboardingTask** checklist layer on top of the O.1 Offboarding Case.

Checklist completion is tracked and exposed (progress / overdue / required flags) but **does not yet determine OffboardingCase completion**. Clearance, exit interview, finalization rules, and AI come later.

## Task model

Table: `offboarding_tasks`

| Field | Notes |
|-------|--------|
| `offboarding_case_id` | FK → case, CASCADE |
| `title` / `description` | Snapshot text |
| `category` | Controlled enum |
| `status` | Task lifecycle |
| `is_required` | Default true; future finalization input |
| `assigned_to_employee_id` | Optional active employee |
| `due_date` | Optional date; not required to be ≤ last working day |
| `completed_at` / `completed_by_user_id` | Set on complete |
| timestamps | Standard |

## Categories

`documents` · `handover` · `equipment` · `access` · `administration` · `other`

## Task statuses / transitions

- `pending` → `in_progress` | `completed` | `skipped`
- `in_progress` → `pending` (reopen, HR only) | `completed` | `skipped`
- `completed` / `skipped` — terminal (immutable)

## Default checklist

In-code `DEFAULT_OFFBOARDING_TASK_TEMPLATES` in `templates.py` (no DB template admin in O.2).

Seeded **atomically** when an OffboardingCase is created (single commit: case + all default tasks).

Roughly 10 tasks across documents, handover, equipment, access, administration. Access tasks are “prepare revocation” only — **no actual revocation**.

## Assignment

Optional. Assignee must exist and be **active**. Assignment does **not** grant HR offboarding authority — only actions on that assigned task (start / complete). Employees cannot skip or edit metadata.

## Authorization

| Actor | Case manage | Create/edit/skip tasks | Start/complete assigned |
|-------|-------------|------------------------|-------------------------|
| HR/Admin | Yes | Yes | Yes (any) |
| Assigned employee | No | No | Own only |
| Unassigned employee | No | No | No |
| Manager (unassigned) | No | No | No |
| Candidate | No | No | No |

## Progress

```
percentage = round(completed_tasks / total_tasks * 100)  # 0 if empty
```

Skipped ≠ completed. Also: required totals, `required_complete` (all required tasks `completed`), `overdue_tasks`.

## Overdue

`due_date < today` AND status ∉ {completed, skipped}. No background scheduler.

## Case / task interaction

Tasks mutable only while case is `initiated` | `in_progress` | `pending_clearance`.

Task changes do **not** auto-change case status. Case `complete` remains lifecycle-only (O.1 temporary rule carries forward until clearance/finalization).

## APIs

HR: `GET/POST /offboarding/{id}/tasks`, `PATCH …/tasks/{task_id}`, `POST …/start|complete|skip|reopen`, `GET …/progress`

Employee: `GET /me/offboarding/tasks`, `POST /me/offboarding/tasks/{id}/start|complete`

## Migration

- Revision: `050_offboarding_tasks`
- Revises: `049_offboarding_cases`

## Deferred

- Clearance domain
- Exit interview / Meet
- Notifications
- AI Offboarding Agent
- Using checklist to gate case completion
- Account deactivation / access revocation automation
- DB-backed configurable templates UI

Future:

```
Offboarding
  ├── Checklist   ← this phase
  ├── Clearance
  ├── Exit Interview
  └── AI Offboarding Agent
```
