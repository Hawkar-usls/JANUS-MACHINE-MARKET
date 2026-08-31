# JANUS COMMERCE AUTHORITY

## Role

`JANUS COMMERCE AUTHORITY` is the proposed commercial authority layer between public machine discovery and the existing JANUS activation / execution authority chain.

It is **not** a payment-controlled backdoor into JANUS.

Target flow:

```text
AI AGENT
→ GitHub discovery
→ JANUS MACHINE MARKET
→ JANUS COMMERCE AUTHORITY
→ quote / 402-compatible payment challenge
→ payment evidence
→ PURCHASE_GRANT
→ Activator
→ execution authority
→ Physarius / target organ
→ result
→ RESULT_RECEIPT
→ buyer
```

## Dual authority boundary

The Commerce Authority creates a commercial eligibility object. It does not perform unrestricted execution.

```text
PAYMENT_RECEIPT
      ↓
PURCHASE_GRANT
      ↓
POLICY + SKU + REQUEST + REPLAY GATES
      ↓
EXECUTION_GRANT
```

The separation is intentional:

```text
PAYMENT != EXECUTION_AUTHORITY
PURCHASE_GRANT != EXECUTION_RESULT
EXECUTION_GRANT != CLAIM_AUTHORITY
RESULT_RECEIPT != EXTERNAL VALIDATION
```

## Purchase grant

A valid future `PURCHASE_GRANT` should bind at minimum:

- `purchase_id`
- `sku`
- `offer_hash`
- `request_hash`
- `terms_hash`
- exact price / settlement rule
- payment reference
- expiry
- nonce / replay domain
- permitted operation
- input and output ceilings
- side-effect class
- authority ceiling

Any mismatch fails closed.

## Idempotency

Commercial retries must not multiply execution:

```text
1 purchase_id + 1 request_hash
=> <= 1 billable execution
```

Repeated delivery of the same accepted purchase should reconcile to the same logical execution and result receipt.

## SKU classes

### DATA / SEARCH

First activation candidate.

Examples:

- `JANUS.SEARCH`
- `JANUS.DATASET_SCOUT`
- `JANUS.EVIDENCE_PACK`
- `JANUS.ARCHIVE_SCAN`
- `JANUS.REPO_AUDIT`

These should remain bounded research / discovery products with explicit provenance and source-license handling.

### INFERENCE / JANUS RUN

Future bounded organ execution such as:

```text
ANALYZE
COMPARE
CLASSIFY
SYNTHESIZE
ROUTE
```

This is not raw unrestricted access to an underlying model.

Current market status: `CLOSED_TARGET_EXECUTION_WITNESS_PENDING`.

### COMPUTE

Future allowlisted compute products may expose verified resource units or declared workload types.

They must not become arbitrary remote shell, arbitrary buyer-code execution, secret access or unrestricted network execution.

Current market status: `CLOSED_TARGET_EXECUTION_WITNESS_PENDING`.

## TARGET EXECUTION WITNESS gate

INFERENCE and COMPUTE remain closed until JANUS has a real persistent witness for the full bounded path:

```text
GRANT
→ TRANSPORT
→ TARGET EXECUTION
→ RESULT
→ RETURN
→ HOME PERSISTENT WITNESS
```

A code path, grant object or CI pass is not equivalent to a witnessed end-to-end execution.

## Physarius position

The market should enter JANUS as an external commercial stimulus, not bypass organism routing.

```text
COMMERCE
→ HOME
→ PHYSARIUS
→ TARGET ORGAN
→ PHYSARIUS
→ HOME
→ BUYER
```

This preserves routing, provenance, authority ceilings, receipts and fail-closed behavior.

## Control-plane rule

GitHub is the public discovery / catalog / request-control surface. It should not be treated as the universal production compute backend.

A future low-latency machine-purchase API requires a continuously available HTTP service capable of issuing a bounded payment challenge, verifying settlement, creating a purchase grant and returning an idempotent result status.

## Result receipt

A mature machine-purchase result should be able to bind:

```text
purchase_id
payment_reference
purchase_grant_hash
execution_grant_hash
request_sha256
result_sha256
sku
organ
runtime
resource_usage
price
settlement_reference
result_reference / inline_result
execution_receipt
```

The receipt proves the declared transaction/execution lineage. It does not by itself prove scientific truth, legal compliance or external validity.
