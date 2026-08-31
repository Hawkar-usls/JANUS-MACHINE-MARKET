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
