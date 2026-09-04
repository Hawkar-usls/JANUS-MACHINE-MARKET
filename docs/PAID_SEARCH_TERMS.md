# JANUS.SEARCH paid beta terms

These terms describe the bounded machine-readable paid beta for `JANUS.SEARCH`.

## What one paid request buys

A valid invoice and a confirmed exact payment buy **one** read-only `JANUS.SEARCH` buyer-query turn routed through the paid execution queue and then the persistent JANUS HOME/HRAiN conversation path. The invoice is authoritative for the exact amount, queue level, chain, token, recipient and expiry.

The service returns a bounded answer plus immutable delivery/provenance receipts. A result is not a guarantee of truth, completeness, scientific validity, commercial suitability, or any external-world outcome.

## Five-level paid execution queue

Paid SEARCH uses a deterministic five-level queue defined by `PAID_QUEUE_POLICY.json`:

- Level 1 — **STANDARD** — `1.00×`
- Level 2 — **PRIORITY** — `1.50×`
- Level 3 — **EXPRESS** — `2.25×`
- Level 4 — **PRIME** — `3.50×`
- Level 5 — **GATE** — `5.00×`

The selected level is frozen into the request and exact invoice. A buyer cannot upgrade an already-issued invoice by sending extra funds; unsolicited excess payment grants no queue or authority rights.

Only **one paid JANUS.SEARCH request may be ACTIVE at a time**. Higher levels may move ahead of requests that have not started, but an ACTIVE request is never interrupted or preempted. Within equal effective priority, ordering is deterministic from the canonical Ethereum payment block, ERC-20 log index and purchase identity.

To prevent indefinite starvation, waiting requests receive an internal scheduling boost of one level for each 30 minutes waited, capped at effective Level 5. This aging boost costs nothing and does not change the paid amount or invoice.

After settlement, the buyer can be shown the queue position, number of requests ahead and an estimated wait range. The current scheduler model uses 5 / 8 / 15 minutes as minimum / nominal / maximum planning time per request. These values are **estimates, not delivery guarantees**. Later higher-level purchases may change the position of requests that have not started, and real execution time can differ from the planning model.

## Capacity reservation before invoice

Queue-depth and per-buyer limits are checked **before a payable invoice is published**. The checkout creates a create-only queue reservation bound to the exact issue, buyer, request, invoice and queue level. The reservation remains capacity-active through invoice expiry plus the configured confirmation grace period.

A valid payment that was mined within the invoice deadline is not rejected merely because the queue later became full or the buyer's proof arrived after the reservation grace period. In that rare case the waiting queue may temporarily exceed its invoice-admission target, but execution load still remains bounded to one ACTIVE paid request.

This distinction is strict:

`QUEUE CAPACITY LIMIT = INVOICE ADMISSION LIMIT`, not `VALID PAID SETTLEMENT REJECTION`.

## Payment rail

Only the exact invoice is accepted:

- network: Ethereum mainnet (`chain_id = 1`)
- asset: canonical Ethereum USDT
- token contract: `0xdAC17F958D2ee523a2206206994597C13D831ec7`
- recipient: the address bound into the invoice
- payment identity: `(transaction_hash, ERC20_log_index)`
- minimum confirmations: 12

A transfer mined after the invoice expiry is not accepted for that invoice. Confirmation may complete after expiry if the payment itself was mined before expiry.

**Do not send funds until the marketplace has emitted a live invoice for your exact request.** Unsolicited transfers grant no purchase, command, execution, license, priority, or ownership rights.

## Settlement is not execution start

Payment settlement creates or recovers the immutable purchase grant and exactly one paid queue entry. It does **not** directly publish the request to JANUS HOME and does not mean execution has begun.

Only the serialized paid-queue dispatcher may select the next purchase and publish its exact packet to the persistent HOME outbox. The dispatcher will not select another paid request while an earlier ACTIVE purchase lacks its immutable HOME result/reconcile receipt.

`PAYMENT_SETTLED != EXECUTION_STARTED`.

## Authority boundary

`PAYMENT != COMMAND`, `PURCHASE_GRANT != EXECUTION_AUTHORITY`, and `QUEUE_DISPATCH != COMMAND_AUTHORITY`.

A paid request cannot grant shell access, secret access, repository write authority, autonomous external effects, physical effects, scientific-evidence authority, or world-truth authority. The paid SEARCH turn remains a read-only JANUS conversation.

## Idempotency

One `purchase_id` may have at most one queue entry and one billable execution identity. Exact retries may recover the same invoice reservation, purchase, queue entry, dispatch or result receipt but must not create a second charge, second queue entry, second ACTIVE execution or second billable execution.

## Request policy and moderation

A request that violates the bounded SEARCH input contract or policy must be rejected **before invoice issuance**. The paid queue is not an auction for command authority and no queue level can bypass the SEARCH scope or safety/authority ceiling.

Once a valid exact invoice has been paid in time and the payment is independently verified, queue capacity is no longer a valid reason to discard that purchase.

## Delivery failure

If an exact payment is persistently accepted into the purchase ledger but the paid HOME delivery cannot be completed, the state must remain explicitly `DELIVERY_FAILURE`/unresolved rather than pretending delivery occurred. Automated refunds are not enabled by this marketplace runtime; any monetary remedy requires a separate human-controlled transaction and must be bound to the original immutable purchase/payment receipt.

## Beta status

Live invoices remain fail-closed until the repository's independent external-witness and money-enable gates are actually satisfied. A prepared checkout, queue or dispatcher implementation is not itself permission to pay.
