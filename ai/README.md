# AI Layer

This directory will contain the decoupled AI platform / agentic microservices layer.

## Planned Components

- **Orchestrator** — routes user requests to specialized agents
- **Agents** — Knowledge, Recruitment, Leave, Training, Document, Onboarding
- **Tools** — interfaces to Core HR business services
- **RAG** — vector-based knowledge retrieval

## Architecture Rule

```
Agent → Tool → Business Service → Database
```

Agents must NEVER directly access the database.

## Status

Not yet implemented. Core HR must be functional first.

See project README for development progression.
