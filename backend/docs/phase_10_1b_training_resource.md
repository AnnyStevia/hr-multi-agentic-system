# Phase 10.1B — Training Resource URL

**Stance:** Metadata-only. No AI/agent/registry, no onboarding state-machine changes, no new permissions or endpoints.

## Why

Catalogue trainings needed an optional link to the real learning resource (LMS, portal, Coursera, docs) so employees and HR can open materials without embedding or server-side fetching.

## Data model

| Table | Change |
|-------|--------|
| `trainings` | Nullable `resource_url` (`String(2048)`) |
| `onboarding_trainings` | **Unchanged** — URL inherited via `Training` relationship |

## Validation

- Optional / nullable.
- Blank string → stored as `null`.
- Non-null: must be `http` or `https` with a netloc (`urllib.parse.urlparse`).
- Rejects other schemes and malformed values.
- Does **not** fetch or probe the remote URL (no SSRF surface).

## API

Existing routes only:

- `POST /api/v1/trainings` — optional `resource_url`
- `PATCH /api/v1/trainings/{id}` — set or clear (`null`) `resource_url`
- `GET /api/v1/trainings` — returns `resource_url`
- Assignment list/create/complete responses include `resource_url` from the related Training

Auth unchanged: catalogue CRUD remains `require_hr_staff` + `training:read` / `training:write`.

## Assignment exposure

`OnboardingTrainingResponse` adds `resource_url` populated from `assignment.training.resource_url`. Source of truth remains the catalogue row.

## Frontend

[`TrainingSection`](../../frontend/src/components/TrainingSection.tsx):

- HR create form: optional Resource URL
- HR catalogue list: edit/clear URL via PATCH
- Assignment cards: external link (`target=_blank`, `rel=noopener noreferrer`) when present

No AI Assistant UI changes.

## Migration

- Revision: **`046_training_resource_url`**
- Revises: `045_application_rejection_reason`
- Reversible: `upgrade` adds column; `downgrade` drops it

## Explicit out of scope

Due dates, mandatory flags, certificates, quizzes, LMS integration, progress tracking, categories, reminders, manager dashboards, bulk assign, Training Agent / AI tools / registry / unified assistant.
