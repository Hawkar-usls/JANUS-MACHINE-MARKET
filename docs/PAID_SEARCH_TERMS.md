# JANUS.SEARCH paid beta terms

These terms describe the bounded machine-readable paid beta for `JANUS.SEARCH`.

## What one paid request buys

A valid invoice and a confirmed exact payment buy **one** read-only `JANUS.SEARCH` buyer-query turn routed through the persistent JANUS HOME/HRAiN conversation path. The current FAST rate is taken from `PRICING.json`; the invoice is authoritative for the exact amount, chain, token, recipient and expiry.

The service returns a bounded answer plus immutable delivery/provenance receipts. A result is not a guarantee of truth, completeness, scientific validity, commercial suitability, or any external-world outcome.

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

## Authority boundary

`PAYMENT != COMMAND` and `PURCHASE_GRANT != EXECUTION_AUTHORITY`.

A paid request cannot grant shell access, secret access, repository write authority, autonomous external effects, physical effects, scientific-evidence authority, or world-truth authority. The paid SEARCH turn remains a read-only JANUS conversation.

## Idempotency

One `purchase_id` may have at most one billable execution identity. Exact retries may recover the same purchase/result receipt but must not create a second charge or second billable execution.

## Delivery failure

If an exact payment is persistently accepted into the purchase ledger but the paid HOME delivery cannot be completed, the state must remain explicitly `DELIVERY_FAILURE`/unresolved rather than pretending delivery occurred. Automated refunds are not enabled by this marketplace runtime; any monetary remedy requires a separate human-controlled transaction and must be bound to the original immutable purchase/payment receipt.

## Beta status

Live invoices remain fail-closed until the repository's independent external-witness and money-enable gates are actually satisfied. A prepared checkout implementation is not itself permission to pay.
