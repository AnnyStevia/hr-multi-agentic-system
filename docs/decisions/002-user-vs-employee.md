# ADR 002: User vs Employee Separation

## Status

Accepted

## Context

Authentication identity and HR business entities serve different purposes.

## Decision

- `User` = authentication / identity (login credentials)
- `Employee` = HR business entity (may link to a User)
- `Candidate` = external entity, no User account required

## Consequences

- Clear separation of concerns
- Candidates can exist without system accounts
- Employee records preserve recruitment history via source application reference
