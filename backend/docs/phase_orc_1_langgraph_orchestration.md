# Phase Orc.1 — Minimal LangGraph orchestration

**Status:** Implemented. Frontend ask/confirm contract unchanged.

## What changed

`POST /api/v1/ai/assistant/ask` now runs a compiled LangGraph instead of inline
availability → route → dispatch glue. Specialist agents, tools, HMAC confirm,
and domain services are unchanged.

```text
START
  → filter_available      (get_available_agents)
  → select_agent          (route_message, deterministic)
  → [agent] invoke_specialist → maybe_allowlisted_handoff → normalize → END
  → [clarify|unavailable] maybe_llm_clarify → normalize → END
                          (optional LLM pick among available ids only; default off)
```

## Modules

| Path | Role |
|------|------|
| `app/ai/orchestration/graph/` | State, nodes, builder, `run_assistant_orchestration` |
| `app/ai/orchestration/handoffs.py` | Allowlisted handoff pairs (empty by default) |
| `app/api/v1/ai_assistant.py` | HTTP envelope + exception mapping; Depends injects specialists |

## Dependencies

- `langgraph==1.0.10`
- `langchain-core==1.6.6` (LangGraph transitive API surface only)
- Specialists still call `LLMProvider` (Gemini / Mistral). No second provider stack.

## Hard constraints preserved

- Frozen `AIExecutionContext` only — graph never rebuilds identity from LLM text
- Availability filter before selection
- One specialist per request; tools stay inside that agent
- Orchestrator never calls `ToolExecutor` / domain writes
- Confirm remains `POST /ai/{domain}/confirm`
- Soft outcomes: `clarification_required` / `unavailable` with `agent_id=null`

## Feature flag (Orc.3)

`AI_ORCHESTRATOR_LLM_CLARIFY` / `ai_orchestrator_llm_clarify` (default `false`).
When true and the deterministic router returns `clarify`, `LLMProvider.generate_structured`
may pick one **available** agent id with high confidence; otherwise clarify answer is kept.

## Standalone agent routes

`POST /ai/{domain}/ask` (+ confirm where applicable) remain direct specialist entry points.
