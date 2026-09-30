# Phase O.4 — Offboarding Exit Interview

## 1. Purpose

Add an **Exit Interview** child of `OffboardingCase` for HR to schedule a Meet-backed conversation, then record free-text feedback.

Separate from recruitment `Interview`. Reuses shared `MeetingProvider` — no new Google integration. Does **not** gate case `complete()`.

## 2. Entity

Table: `exit_interviews`

| Field | Notes |
|-------|--------|
| `offboarding_case_id` | FK CASCADE |
| `interviewer_employee_id` | FK employees SET NULL |
| `created_by_user_id` | FK users SET NULL |
| `scheduled_at` / `ends_at` | timestamptz (required for Meet) |
| `meeting_url` / `meeting_external_id` | Same sizes as recruitment interviews |
| `status` | `scheduled` \| `completed` \| `cancelled` |
| `feedback` | Free text |
| `completed_at` | Set on complete |

Partial unique: one active (`scheduled`/`completed`) per case. Cancelled rows allow reschedule.

Migration: **`053_offboarding_exit_interview`**.

## 3. Meet reuse

`ExitInterviewMeetingService.ensure_meeting` mirrors interview orchestration via `get_meeting_provider()`, soft-fail, repair, idempotency key `exit-interview-{id}`. Background runner after schedule + HR `POST .../meeting` retry.

## 4. API

| Method | Path | Auth |
|--------|------|------|
| GET/POST/PATCH | `/offboarding/{case_id}/exit-interview` | read / write |
| POST | `.../complete`, `.../cancel`, `.../meeting` | write |
| GET | `/me/offboarding/exit-interview` | employee (own active case) |

## 5. Notifications

- `exit_interview_scheduled`
- `exit_interview_meeting_ready`

## 6. Non-goals

Questionnaire, AI, case-complete gating, recruitment Interview coupling, new Google OAuth.
