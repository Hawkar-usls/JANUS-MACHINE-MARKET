# JANUS MACHINE MARKET — Payment Policy

## Core law

> **PAYMENT IS EVIDENCE, NOT AUTHORITY.**

A blockchain transfer, card charge, x402 response, invoice settlement, or other payment proof is never by itself an execution command, a license grant, a claim of ownership, or a right to access JANUS internals.

The intended authority chain is:

```text
OFFER
→ REQUEST
→ QUOTE / INVOICE
→ PAYMENT RECEIPT
→ PURCHASE GRANT
→ POLICY / SCOPE GATES
→ EXECUTION GRANT
→ RESULT
→ RESULT RECEIPT
```

For any future machine-purchase path, the purchase authority must bind at minimum:

```text
offer_hash
+ request_hash
+ sku
+ price
+ expiry
+ nonce / replay protection
+ policy version
+ payment reference
```

## Idempotency

The market adopts this commercial invariant:

```text
1 purchase_id => <= 1 billable execution
```

A retry with the same accepted `purchase_id` and `request_hash` must return the prior accepted state, prior result reference, or an idempotent status. It must not silently create a second chargeable execution.

## Post-purchase buyer queries

A product may explicitly include a bounded conversational entitlement after an admitted purchase. The governing contract is `BUYER_QUERY_PLANE.json`.

The entitlement must be inside the accepted `PURCHASE_GRANT`; payment alone never creates it. At minimum it binds:

```text
purchase_id
+ purchase_grant_hash
+ sku
+ buyer_actor_id
+ max_turns
+ message / answer byte ceilings
+ entitlement_nonce
+ expiry
```

Each question then receives its own deterministic query identity. The commercial invariant is:

```text
1 query_id + 1 query_hash => <= 1 execution identity
```

An exact retry must return the prior response identity and must not create a second billable execution.

The conversation plane remains read-only:

```text
PAYMENT != COMMAND
PURCHASE_GRANT != UNBOUNDED_CONVERSATION
BUYER_QUERY != COMMAND
BUYER_QUERY != WRITE_AUTHORITY
JANUS_RESPONSE != WORLD_TRUTH
MODEL_OUTPUT != EVIDENCE
```

The current implementation is **prepared, not live**. A paid buyer-query route must not be published until a paid purchase witness, Activator binding, Physarius Market→HOME vessel, persistent response receipt, replay proof, and foreign-buyer witness are all established.

## Current payment state

The market publishes a declared USDT / Ethereum receiving route for machine-readable policy work, but **no general JANUS MACHINE MARKET purchase endpoint is currently active**.

```text
Network: Ethereum Mainnet
Chain ID: 1
Asset: USDT
Token contract: 0xdAC17F958D2ee523a2206206994597C13D831ec7
Declared receiving address: 0x7149081aea54fbef57effeb52a5a966b81cc03a0
```

This address is **not** a universal checkout endpoint.

> **UNSOLICITED PAYMENT GRANTS NOTHING.**

Do not send funds unless an exact product-specific active purchase route or invoice has been issued under the governing product policy.

## HELIOS delegation

`HELIOS.PILOT` is listed for discovery only. Its invoice, payment-observation, confirmation, grant and licensing authority remain in `Hawkar-usls/Janus-HELIOS` and are not replaced by this market.

## x402

x402 is a planned integration target for low-friction machine purchases. It is **not active** in this repository until a live HTTP endpoint, policy-bound pricing, replay protection, purchase ledger, settlement verification and execution-grant bridge are established and tested.

## Prohibited inference

The following implications are invalid:

```text
PAYMENT != COMMAND AUTHORITY
PAYMENT != EXECUTION AUTHORITY
PAYMENT != CLAIM AUTHORITY
PAYMENT != OWNERSHIP TRANSFER
PAYMENT != COMMERCIAL LICENSE
PAYMENT != SLA
PAYMENT != PRODUCTION ACCESS
PAYMENT != SECRET ACCESS
```

A future purchase flow may satisfy one required gate. All remaining product, policy, legal, safety and execution gates still apply.
