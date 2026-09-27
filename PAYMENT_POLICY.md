# JANUS MACHINE MARKET — Payment Policy

## Core law

> **PAYMENT IS EVIDENCE, NOT AUTHORITY.**

A blockchain transfer, card charge, x402 response, invoice settlement, or other payment proof is never by itself an execution command, a license grant, a claim of ownership, or a right to access JANUS internals.

The live authority chain for paid `JANUS.SEARCH` is:

```text
OFFER
→ REQUEST
→ QUEUE CAPACITY RESERVATION
→ QUOTE / INVOICE
→ PAYMENT RECEIPT
→ PURCHASE GRANT
→ PAID QUEUE ENTRY
→ SERIALIZED QUEUE DISPATCH
→ POLICY / SCOPE GATES
→ PERSISTENT HOME EXECUTION
→ RESULT
→ RESULT RECEIPT
```

The purchase authority binds at minimum:

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

## Seller activation and witness evidence

Paid `JANUS.SEARCH` seller commerce is explicitly authorized by `COMMERCE_READINESS.json` and the product contract. `FOREIGN_AGENT_WITNESS` is an evidentiary state describing whether a qualifying independent external principal has already completed the frozen persistent-HOME roundtrip. It is **not** seller permission and is not required merely to issue a legitimate paid invoice.

```text
SELLER_COMMERCE_AUTHORIZED != FOREIGN_AGENT_WITNESS
CUSTOMER_CAN_BUY != WITNESS_ALREADY_OBSERVED
```

A real qualifying customer delivery may later provide the evidence needed to promote `FOREIGN_AGENT_WITNESS`, but the flag must never be fabricated from owner/self/synthetic traffic.

## Live USDT / Ethereum route

`JANUS.SEARCH` has a live issue-based exact-invoice checkout route.

```text
Network: Ethereum Mainnet
Chain ID: 1
Asset: USDT
Token contract: 0xdAC17F958D2ee523a2206206994597C13D831ec7
Declared receiving address: 0x7149081aea54fbef57effeb52a5a966b81cc03a0
Required confirmations: 12
```

The receiving address alone is **not** a universal checkout endpoint. The buyer first opens a `[JANUS PAID SEARCH]` issue. JANUS reserves queue capacity and posts an exact invoice bound to that request. Only the exact invoice amount, token, receiver and validity window are accepted for that purchase.

> **UNSOLICITED PAYMENT GRANTS NOTHING.**

## Live BTT / TRON route

`JANUS.SEARCH` also has a live exact-invoice route for the post-redenomination **BitTorrent Token**, paid as **BTT TRC-20 on TRON Mainnet**. The buyer opens a `[JANUS PAID SEARCH BTT]` issue; a published wallet address by itself is not an order.

The route is frozen by `BTT_PAYMENT_ROUTE.json`:

```text
canonical USDT reference total
→ apply BTT route discount of 50%
→ fetch fresh Binance BTTCUSDT best bid / ask
→ enforce bounded order-book spread
→ freeze midpoint + observation timestamp in the invoice
→ compute exact BTT amount
→ CEILING to the 18-decimal BTT atomic unit
→ bind token contract + receiver + amount + expiry + request hash
```

The names are intentionally explicit:

```text
payment asset = BTT / BitTorrent Token
Binance exchange ticker = BTTC
Binance market symbol = BTTCUSDT
network = TRON Mainnet
standard = TRC-20
new-token contract = TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4
```

`BTTC` in the oracle does **not** mean JANUS accepts a different asset. It is Binance's ticker for the post-redenomination BitTorrent Token market. The payment proof must still be the exact BTT TRC-20 transfer specified by the invoice. BTTOLD is not accepted.

The declared receiver is `TSqkDJX9uBEnA8mmRc4UN3Bw6hcujcvmd1`.

Settlement is admitted only from TRON solidified state. JANUS requires both the solidified transaction body and the solidified execution receipt, successful smart-contract execution, the exact BTT token contract, the exact receiver, and the exact atomic amount. Replay identity is `tron:<txid>:<event_index>`.

> **DO NOT SEND BTT WITHOUT AN EXACT LIVE JANUS BTT INVOICE.**

A published receiving address does not create an order, settlement, purchase grant, execution grant, refund obligation, or delivery obligation.

## Idempotency

The market adopts this commercial invariant:

```text
1 purchase_id => <= 1 billable execution
1 Ethereum tx_hash + 1 ERC20 log_index => <= 1 accepted purchase
1 TRON txid + 1 TRC20 event_index => <= 1 accepted purchase
1 settled purchase => <= 1 paid queue entry
1 paid SEARCH runtime => <= 1 ACTIVE paid execution at a time
```

A retry with the same accepted `purchase_id` and `request_hash` must return the prior accepted state, prior queue/dispatch state, prior result reference, or an idempotent status. It must not silently create a second chargeable execution.

## Paid SEARCH queue boundary

The five-level scheduler is governed by `PAID_QUEUE_POLICY.json`.

A queue level changes only the order among requests that have **not started**. It does not grant command authority, broaden the product scope, or permit an active request to be interrupted. The current active execution cap is exactly one paid `JANUS.SEARCH` request.

Queue-depth and per-buyer limits are checked before a payable invoice is published. A create-only reservation binds capacity to the exact issue/request/invoice. Once an exact payment was validly included within the invoice deadline and independently verified, later queue fullness is not a lawful reason to discard the purchase.

```text
QUEUE CAPACITY LIMIT = INVOICE ADMISSION LIMIT
PAYMENT_SETTLED != EXECUTION_STARTED
HIGHER_QUEUE_LEVEL != PREEMPT_ACTIVE_EXECUTION
QUEUE_DISPATCH != COMMAND_AUTHORITY
```

After settlement, execution starts only when the serialized queue dispatcher selects that purchase and publishes its exact paid HOME packet. Waiting position and ETA are planning estimates, not a guaranteed completion time.

## Post-purchase buyer queries

The live paid `JANUS.SEARCH` product includes one bounded read-only buyer-query entitlement after an admitted purchase. The governing contract is `BUYER_QUERY_PLANE.json`.

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

Each question receives its own deterministic query identity:

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

## HELIOS delegation

`HELIOS.PILOT` is listed for discovery only. Its invoice, payment-observation, confirmation, grant and licensing authority remain in `Hawkar-usls/Janus-HELIOS` and are not replaced by this market.

## x402

x402 has two independent authority directions and they MUST NOT share a gate implicitly.

### JANUS as x402 seller

Native HTTP x402 selling remains separate from the live GitHub-issue USDT/BTT seller paths. JANUS must not advertise an x402 seller endpoint until a real HTTP resource, policy-bound pricing, replay protection, settlement verification and HOME delivery binding are actually deployed.

```text
JANUS_X402_SELLER
!= JANUS_GITHUB_ISSUE_USDT_BTT_SELLER
!= JANUS_X402_BUYER
```

### JANUS as x402 buyer

A tightly bounded external x402 purchase may run independently under `X402_BUYER_POLICY.json`.

Current pilot authority is intentionally narrow:

```text
OWNER_AUTHORIZED_BOUNDED_BUYER_PILOT_ENABLED
resource = https://api.mach.gallery/api/base/block-number
method = GET
network = Base mainnet / eip155:8453
asset = native Circle USDC on Base
max payment = 5000 atomic USDC = 0.005 USDC
max rolling 24h spend = 5000 atomic USDC
```

The runtime is `runtime/x402_buyer_call.mjs`; the explicit operator-triggered workflow is `.github/workflows/x402-buyer-mach-live.yml`.

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

A purchase flow may satisfy one required gate. All remaining product, policy, legal, safety and execution gates still apply.
