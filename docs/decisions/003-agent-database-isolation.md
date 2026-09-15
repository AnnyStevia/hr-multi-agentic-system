# ADR 003: Agents Never Access Database Directly

## Status

Accepted

## Context

LLMs must not be the authority over business rules, data integrity, or permissions.

## Decision

All agent actions must follow:

```
Agent → Tool → Business Service → Database
```

## Consequences

- Business rules remain deterministic in the backend
- Agents are enhancement layer, not data layer
- Audit trails and permissions enforced at service level
