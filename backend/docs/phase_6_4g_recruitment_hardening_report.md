# Phase 6.4G — Recruitment AI Hardening Final Report

## 1. Recruitment architecture audit

Chain verified: Frontend (`/hr/*` assistant) → `POST /ai/recruitment/ask|confirm` → `RecruitmentAgent` → `ToolExecutor` → tools → Application/Interview/Meeting/Employee services → DB.

AI does not call repositories, ORM (except audit Session + `get_user`), SQL, or Google APIs directly. Meet goes through `InterviewMeetingService.ensure_meeting` / MeetingProvider.

Write tools (all confirmation-gated): `shortlist_application`, `reject_application`, `create_interview_invitation`, `retry_interview_meeting`, `record_interview_outcome`.

## 2. Issues found

- Reject reason not persisted
- Reject did not notify candidate
- Confirm answer dumped raw tool JSON
- Confirm API 502 could leak internal messages
- HMAC secret fallback to hardcoded string when unset
- Reject allowed while active interview exists
- Confirmation expiry / audit phases / AI outcome / replay undertested

## 3. Issues fixed

- Alembic `045_application_rejection_reason`; HR-only `rejection_reason` on reads
- Reject notification via `APPLICATION_STATUS_CHANGED`
- Active-interview reject blocked (409)
- Confirm answer sanitized (`_format_confirm_answer`)
- Confirm 502 generic; FE recruitment 409 sanitized
- HMAC secret hard-fail when empty
- Expanded confirmation/audit/outcome/replay tests + E2E demo

## 4. Remaining limitations

See §20.

## 5. Write tools audited

All five gated via `may_require_confirmation` + HMAC confirm + re-authorize + service validation.

## 6. Confirmation security result

HMAC binds user, tool_name, arguments, expiry. Tamper / wrong user / expired fail. Replay after successful shortlist fails via state machine. One-time `jti` deferred (domain state sufficient except intentional Meet idempotency).

## 7. AI audit result

`ai_tool_action_audits`: phases `proposed|confirmed|executed|failed`; stores digest/ids/codes only. Covered by unit + integration tests.

## 8. Permission matrix (actual)

| Capability | Candidate | Employee | HR/Admin |
|---|---|---|---|
| Own application data | yes | no | yes |
| Fit score | no | no | yes (`recruitment:read`) |
| Recruitment Agent ask | no | no | yes (`recruitment:read`) |
| Recruitment Agent confirm | no | no | yes (`recruitment:write`) |
| Interview internal / feedback (HR APIs + agent) | no | panel via `/me` only | yes |
| Propose slots | no | primary only | no |
| Submit official feedback | no | primary only | no (HR records outcome) |
| Create invitation / hire-reject / retry Meet | no | no | yes (`recruitment:write`) |
| Meeting URL | own interview | assigned interviewer | yes |

## 9. Interview state-machine result

PROPOSED → SCHEDULED → COMPLETED → outcome. No cancel writer. Primary invariant at invite. Recommendation never auto-hires.

## 10. Google Meet integration result

AI never calls Google; `retry_interview_meeting` → `ensure_meeting` (idempotent). CI uses FakeMeetingProvider. No live Google run in 6.4G.

## 11. Notification result

Service-side only (shortlist, reject, interview lifecycle, Meet ready, outcomes). Tools do not create Notification rows.

## 12. Entity resolution result

IDs only; `find_employees` clarifies on 0/many. Fixed earlier `employment_status` bug.

## 13. Idempotency result

Shortlist/reject/invite/outcome: duplicate confirm rejected by state. Meet retry: intentionally idempotent.

## 14. Adversarial prompt test result

Prompt unit asserts confirmation / no invent / recommendation ≠ hire. No live-LLM adversarial suite (SAFE TO DEFER). Manual checklist recommended for demo.

## 15. End-to-end scenario result

`test_ai_recruitment_e2e_demo.py`: ask → pending shortlist → confirm → audit → re-read shortlisted. PASS (mocked LLM).

## 16. Tests added

- Confirmation expiry, body tamper, confirm formatting, prompt rules, record_outcome gate, audit phases
- Reject reason + notify + replay integration
- E2E demo integration

## 17. Exact final test counts

- Unit suite: **336 passed**
- Key integrations (AI + interview + meetings + invitations + outcomes + notifications + hire/onboarding smoke): **71 passed**
- Targeted 6.4G confirmation/writes/e2e: **34 passed**

## 18. Alembic head

`045_application_rejection_reason`

## 19. frontend tsc/build

`tsc --noEmit` + `next build`: **passed**

## 20. Classifications

**SAFE TO DEFER**

- One-time confirmation `jti` store
- Full application status history table
- Ask-path auth-deny audit
- Chat history / Markdown renderer / visual polish
- Automated live-LLM adversarial suite
- Live Google smoke (unless Meet regression suspected)
- Panel immutable after invite; extra panelists not notified at invite

**KNOWN LIMITATION**

- No cancel/reschedule (`CANCELLED` unused)
- No post-invite primary/panel mutation
- Slot proposal primary-only (not HR/agent)
- NL “yes” without FE Confirm does not authorize writes
- Interviewer recommendation ≠ HR decision (by design)

**MUST FIX BEFORE NEXT AGENT**

- None remaining for Recruitment AI closure

## 21. Completeness statement

**Recruitment AI is ready to be considered functionally complete.**
