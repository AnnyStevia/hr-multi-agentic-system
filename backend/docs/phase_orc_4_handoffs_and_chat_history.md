# Phase Orc.4 — Allowlisted handoffs + chat-history persistence (design)

**Status:** Design + no-op handoff hook. Persistence not implemented.

## Multi-agent handoffs

### Product rule

Default remains **one specialist per ask**. Free fan-out / shared tool pools are rejected
(auth leakage, invented workflows).

### Allowlist

Module: [`app/ai/orchestration/handoffs.py`](../app/ai/orchestration/handoffs.py)

```python
ALLOWLISTED_HANDOFFS: frozenset[tuple[str, str]] = frozenset({
    # Example when product enables:
    # ("offboarding", "knowledge"),  # case answer then policy cite only
})
```

`is_handoff_allowed(source, target)` is true only for explicit pairs; self-handoffs denied.

### Graph hook (no-op today)

Node `maybe_allowlisted_handoff` runs after `invoke_specialist`. With an empty allowlist
and no `handoff_target` in state, it clears handoff fields and continues to normalize.

**Future sequential hop (not shipping):**

1. Primary specialist `ask` completes (answer + optional pending_confirmation).
2. If product sets an allowlisted `(source, target)` and the hop is **read-only**
   (e.g. Knowledge cite), invoke `target.ask` with the **same** frozen context.
3. Treat the primary answer as untrusted DATA in the secondary prompt.
4. Never merge tool registries; never auto-confirm writes on either hop.
5. Envelope keeps the **primary** `agent_id` for confirm routing if a write was proposed;
   secondary text may append to `answer` only when documented.

Ambiguous multi-intent (“prepare everything for departure”) stays **clarify** unless
product later defines an allowlisted sequence.

---

## Chat-history persistence (schema design only)

Do **not** implement storage in this phase. When added, graph/HTTP should be able to
record the fields below without changing the FE ask envelope.

### Recommended tables (sketch)

**`ai_conversations`**

| Column | Notes |
|--------|-------|
| `id` (UUID) | `conversation_id` |
| `user_id` | FK; never trust LLM-claimed user |
| `created_at` / `updated_at` | UTC |
| `title` | Optional short label |

**`ai_conversation_messages`**

| Column | Notes |
|--------|-------|
| `id` (UUID) | `message_id` |
| `conversation_id` | FK |
| `role` | `user` \| `assistant` \| `system` |
| `content` | User text / assistant answer (retention-policy subject) |
| `created_at` | UTC |
| `agent_id` | Nullable; specialist that answered |
| `route_reason` | From `route_message` / llm_clarify |
| `node_path` | JSON list of graph node names |
| `status` | `completed` \| `clarification_required` \| `unavailable` \| `error` |
| `error_code` | Optional soft/hard error code |
| `tool_names_called` | JSON string list; **no** raw args/secrets |
| `pending_confirmation_digest` | Hash/digest of token if proposed; **not** raw HMAC |
| `pending_confirmation_expires_at` | Optional |
| `pending_resolved` | bool / null |
| `model` | Optional model id |
| `usage_json` | Optional token usage |

### Explicit non-goals for storage

- Do not persist full confirmation tokens long-term (prefer digest + expiry).
- Do not dump tool argument payloads / PII-heavy service responses without a retention policy.
- Do not store role/permission claims from model text; identity remains JWT/DB context at request time.

### Write timing

- After successful `normalize_envelope` (or HTTP exception mapping for hard failures).
- Confirm actions update `pending_resolved` on the originating message row when confirm succeeds/fails/expires.

### Compatibility

Recording history must be additive. `AssistantAskResponse` fields used by the FE
(`agent_id`, `answer`, `citations`, `pending_confirmation`) stay stable; optional
`conversation_id` / `message_id` can be added later behind the same ask route.
