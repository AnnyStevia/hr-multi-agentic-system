# Google Meet integration (Phase 6.4D / 6.4D.1)

## Architecture

Interview scheduling (Phase 6.4C) is unchanged. After a candidate confirms a slot and the interview is committed as `scheduled`, a **BackgroundTasks** worker provisions a Meet link:

```
confirm_slot (commit SCHEDULED)
  → notify interview_scheduled
  → BackgroundTasks: run_interview_meeting_provision(interview_id)
       → InterviewMeetingService.ensure_meeting
       → MeetingProvider.create_meeting
       → persist meeting_url + meeting_external_id
       → notify interview_meeting_ready (create_if_absent)
```

Application code depends on `MeetingProvider` (`backend/app/shared/meetings/`), not Google SDK types.

| Provider | When |
|----------|------|
| `noop` | Default / incomplete Google config |
| `fake` | Tests / local UI without Google |
| `google` | Calendar API + conferenceData |

## Google API mechanism

**Google Calendar API** `events.insert` with `conferenceDataVersion=1` and `conferenceData.createRequest` (`hangoutsMeet`) creates a Meet conference on a **single organizer** OAuth account.

If the insert response has conference status `pending` (or no `hangoutLink` yet), the provider polls `events.get` a bounded number of times (~5 × 1.5s) before raising a controlled `MeetingProviderError`.

Why not Meet Spaces API: Calendar + conferenceData is the standard timed-meeting approach and fits a shared organizer model without per-user Google login.

Scope used (keep narrow): `https://www.googleapis.com/auth/calendar.events` only.

## Prerequisites (exact)

1. **GCP project** — create or pick a project in [Google Cloud Console](https://console.cloud.google.com/).
2. **Enable Calendar API** — APIs & Services → Library → “Google Calendar API” → Enable.
3. **OAuth consent screen** — External (or Internal for Workspace-only). Add the organizer as a **test user** while the app is in Testing.
4. **Desktop OAuth client** — Credentials → Create credentials → OAuth client ID → Application type **Desktop app**. Download the JSON.
   - Local helper uses redirect `http://localhost` (InstalledAppFlow / `run_local_server`).
5. **Organizer Google account** — the account that will own Calendar events. **Google Workspace** is typically required for Meet conference creation on Calendar; consumer Gmail often fails to attach Meet.
6. **One-time refresh token** — run the helper below; paste values only into ignored `backend/.env`.

## Environment variables

Put these in `backend/.env` (gitignored). Never commit secrets.

```bash
MEETING_PROVIDER=google
GOOGLE_MEET_CLIENT_ID=
GOOGLE_MEET_CLIENT_SECRET=
GOOGLE_MEET_REFRESH_TOKEN=
GOOGLE_MEET_CALENDAR_ID=primary
GOOGLE_MEET_ORGANIZER_EMAIL=   # documentation / future use
```

| Name | Purpose |
|------|---------|
| `MEETING_PROVIDER` | `noop` \| `fake` \| `google` |
| `GOOGLE_MEET_CLIENT_ID` | OAuth Desktop client id |
| `GOOGLE_MEET_CLIENT_SECRET` | OAuth client secret |
| `GOOGLE_MEET_REFRESH_TOKEN` | Offline refresh token for the organizer |
| `GOOGLE_MEET_CALENDAR_ID` | Usually `primary` |
| `GOOGLE_MEET_LIVE_SMOKE` | Set `1` only when running the live smoke script |

## Obtain refresh token (one-time)

```bash
cd backend
# optional: pip install google-auth-oauthlib
.\.venv\Scripts\python.exe scripts/obtain_google_meet_refresh_token.py path\to\client_secret.json
```

Or with `GOOGLE_MEET_CLIENT_ID` / `GOOGLE_MEET_CLIENT_SECRET` already in the environment (no JSON path).

The script:

- Opens a browser consent flow with `access_type=offline` and `prompt=consent`
- Requests **only** `calendar.events`
- Prints the refresh token **once** — paste into `backend/.env`; it never writes secrets into the repo

If no refresh token appears, revoke the app under [Google Account permissions](https://myaccount.google.com/permissions) and re-run.

## Local development (no Google)

- Leave `MEETING_PROVIDER=noop` — interviews schedule without a link; UI shows “Meeting link will appear shortly.”
- Use `MEETING_PROVIDER=fake` to exercise Join UI and notifications without Google.
- HR can call `POST /api/v1/interviews/{id}/meeting` to retry provisioning.

## Live smoke (Phase 6.4D.1)

Opt-in only. Claims live Meet success **only** if Google returns a real `meet.google.com` URL.

```bash
cd backend
# Ensure backend/.env has MEETING_PROVIDER=google and all GOOGLE_MEET_* filled
$env:GOOGLE_MEET_LIVE_SMOKE="1"
.\.venv\Scripts\python.exe scripts/smoke_google_meet.py
```

What it does:

1. Refuses fake/noop providers and missing env vars (prints a checklist).
2. Creates a short-lived event titled `[HR-SMOKE] …` (~+20 min, 15 min duration).
3. Confirms Meet URL + external event id (pending poll handled in the provider).
4. Calls `get_meeting` and compares the URL.
5. Deletes the event; on cleanup failure prints the event id for manual delete.
6. Prints summary: conference status, Meet URL YES/NO, cleanup OK/FAILED — **never** tokens.

Expected success: `meet_url: YES`, a `https://meet.google.com/...` line, `cleanup: OK`, `result: PASS`, `ok`.

If credentials are missing or Google rejects the call, the script **STOP**s with the failing step — do not treat mock/fake runs as live validation.

## Failure / retry

- Scheduling never rolls back if Google fails.
- Idempotency: existing `meeting_url` is returned; `meeting_external_id` avoids blind duplicate creates.
- Retries use `ensure_meeting` (background or HR endpoint).
- Pending conference timeout raises a sanitized provider error (no aggressive retries in unit tests).

## Known limitations

- Single organizer calendar; interviewers do not need Google accounts in-app.
- Attendee invites are best-effort; the platform join URL is the source of truth.
- No reschedule / cancel sync of the Calendar event (no reschedule engine in 6.4C).
- Service-account domain-wide delegation is deferred; OAuth refresh token is the supported path.
- Workspace accounts are often required for Meet on Calendar; consumer Gmail may fail conference creation.
