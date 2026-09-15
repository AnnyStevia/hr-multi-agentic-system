# ADR 001: Modular Monolith for Core HR

## Status

Accepted

## Context

The Core HR platform needs clear module boundaries while remaining simple to develop and deploy for a PFE project.

## Decision

Implement Core HR as a modular monolith using FastAPI with domain modules under `backend/app/modules/`.

## Consequences

- Single deployable unit simplifies development
- Module boundaries enforced via service interfaces
- Can extract modules to microservices later if needed
