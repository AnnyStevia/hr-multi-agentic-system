# Phase O.6C — Unified Assistant Integration (Offboarding)

Registers the Offboarding Agent in the Unified Assistant. No second agent.

## Endpoints

| Path | Role |
|------|------|
| `POST /api/v1/ai/offboarding/ask` | Standalone |
| `POST /api/v1/ai/offboarding/confirm` | Confirmation-gated writes (O.6D) |
| `POST /api/v1/ai/assistant/ask` | Unified: registry → route → same `OffboardingAgent` |

Unified response: `agent_id="offboarding"`; may include `pending_confirmation` for writes. FE Confirm calls `/ai/offboarding/confirm`.

## Registry

- `id`: `offboarding`
- `display_name`: Offboarding Agent
- `supports_confirmation`: **true** (O.6D)
- `required_permissions_any`: `offboarding:read` (HR gate; employees use availability special-case)

## Availability (not tool authorization)

| Actor | Available when |
|-------|----------------|
| Employee | `context.employee_id` is set |
| HR / Admin | staff role **and** `offboarding:read` |
| Manager | only if they independently match Employee or HR/Admin above |
| Candidate | unavailable |

Tools remain authoritative for HR vs self vs cross-employee access.

## Routing markers (deterministic)

Strong / case markers include: offboarding, offboard, leaving the company, departure, last working day, exit interview, offboarding clearance, clearance for departure, offboarding tasks, return laptop/badge/equipment, pending clearance, offboarding progress/status, ready/complete offboarding, employee departure, before leaving, account deactivation (offboarding context).

**Prefer Knowledge** for general resignation / departure **policy** questions without case markers (e.g. “What is the company resignation policy?”).

Leave, Training, Documents, Onboarding, Recruitment routing is unchanged for their own intents.

## Capabilities

Reads (O.6B): case, progress, tasks, clearance, exit interview, readiness, HR employee lookup.

Writes (O.6D, confirmation-gated): `complete_offboarding_case`, `update_offboarding_clearance`, `update_offboarding_task`. See [`phase_offboarding_6d_writes.md`](phase_offboarding_6d_writes.md).

## Scope

- **Employee:** own case reads; assigned task start/complete only (no case complete, no clearance).
- **HR/Admin + permissions:** authorized cases and writes.
- **Managers / candidates:** unavailable at registry unless they independently satisfy Employee or HR rules; tools still deny unauthorized access.
