# Offboarding Account Deactivation

## Purpose

When HR completes an offboarding case (after O.5 readiness rules), the departing employee's **application account** is deactivated. Historical Employee and User rows are kept.

## Account activity

- Login / JWT gate: `User.is_active` (`identity.User`)
- Employment record: `Employee.employment_status` set to `inactive` in the same transaction

## Flow

`POST /api/v1/offboarding/{case_id}/complete` (`offboarding:write`, HR/Admin only):

1. Lock case; require `pending_clearance`
2. Existing O.5 `can_complete` (unchanged)
3. Mark case `COMPLETED`
4. Set case employee `employment_status = inactive`
5. If `employee.user_id` is set → `AuthService.deactivate_user` (`is_active = False`, flush)
6. Single `OffboardingRepository.save` commit

Target user comes only from the case employee — never from the request body.

## Non-goals

No migration, no AI, no checklist/clearance/exit-interview rule changes, no user deletion.
