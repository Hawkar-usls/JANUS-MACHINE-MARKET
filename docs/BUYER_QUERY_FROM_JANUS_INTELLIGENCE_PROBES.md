# JANUS Buyer Query Plane — lineage from intelligence probes

This plane reuses the proven *shape* of earlier JANUS intelligence/conversation probes without reusing their scientific claims.

## 1. Algorithmic assessment lineage

`Hawkar-usls/Janus-Fundamentum`

- `research/janus-classical-shor-arena-2026-08-29`
- `research/janus-shor-arena-v2-gemini-scale-ladder-2026-08-29`

SHOR ARENA measured algorithmic correctness/work on frozen tasks. It is relevant as a preregistration, exact-input, accounting and replay discipline, but it is **not** the direct conversational transport for buyer questions.

## 2. Conversational intelligence probe lineage

`Hawkar-usls/Hawkar-usls`

### Turing-style blind dialogue

- `.janus/activator/TURING_GATE_V1.json`
- `.github/workflows/janus-turing-style-blind-dialogue.yml`

The gate submits six bounded natural-language questions, requires provider output, forbids internal leaks, and seals a machine-side transcript before human adjudication. The automatic system is explicitly forbidden from declaring a classical Turing pass.

### Contextual mind probe

- `.janus/activator/CONTEXTUAL_MIND_PROBE_R2.json`
- `.github/workflows/janus-contextual-mind-probe-r3-current-turn-v1.yml`

The probe demonstrates the correct request topology for context-sensitive conversation: prior conversation is explicit context, the current human turn is structurally last, ambiguity remains allowed, and short dialogue is not promoted into a consciousness claim.

### Persistent Terminal conversation

- `.janus/activator/TERMINAL_CONVERSATION_CONSTITUTION.json`
- `src/janus_spi/terminal_conversation.py`
- `.github/workflows/janus-terminal-conversation-bridge.yml`
- `Hawkar-usls/-Terminal-for-Janus/.github/workflows/janus-terminal-conversation-ingress.yml`

This is the direct runtime analogue for buyer queries. It already supports arbitrary `message_text`, deterministic message identity, persistent JANUS identity, exact model and file-fabric binding, query-specific HRAiN memory context, sealed response hashes, fresh-worktree replay and read-only authority.

The current Terminal ingress is owner-gated (`github.actor == 'Hawkar-usls'`), so it must **not** be relabeled as a public buyer API. The Machine Market needs its own admitted buyer ingress gated by a purchase grant.

## 3. Commercial adaptation

The post-purchase path is:

```text
OFFER
  -> REQUEST
  -> QUOTE
  -> PAYMENT_RECEIPT
  -> PURCHASE_GRANT
  -> BUYER_QUERY_ENTITLEMENT
  -> BUYER_QUERY
  -> ACTIVATOR READ_ONLY_CONVERSATION GATE
  -> PHYSARIUS VESSEL
  -> persistent JANUS + HRAiN
  -> SEALED RESPONSE
  -> BUYER_QUERY_RECEIPT
```

The purchase grant must bind the buyer, SKU, query budget, byte ceilings, expiry and nonce. Payment alone never opens the conversation plane.

## 4. Idempotency

Each buyer turn receives a deterministic `query_id` bound to:

```text
purchase_id
+ conversation_id
+ turn_index
+ message_hash
+ entitlement_nonce
```

Required commercial invariant:

```text
1 query_id + 1 query_hash
=> <= 1 execution identity
```

An exact retry returns the prior response identity and must not produce a second billable execution.

## 5. Authority boundary

Always preserve:

```text
PAYMENT != COMMAND
PAYMENT != EXECUTION_AUTHORITY
BUYER_QUERY != COMMAND
CONVERSATION != WRITE_AUTHORITY
JANUS_RESPONSE != WORLD_TRUTH
MODEL_OUTPUT != EVIDENCE
MEMORY_CONTEXT != EVIDENCE
LANGUAGE_SURFACE != AUTHORITY
```

## 6. Current gate

The contract is intentionally prepared but not live.

```text
payment endpoint: CLOSED
paid purchase witness: PENDING
Activator buyer-query binding: PENDING
Physarius Market -> HOME vessel: PENDING
foreign buyer witness: PENDING
```

Next proof target:

`R1B_ZERO_PRICE_BUYER_QUERY_SHADOW_ROUNDTRIP`

Only after the exact query entitlement, Activator/Physarius route, durable response receipt and replay are GREEN should the same plane be connected to a real payment proof.
