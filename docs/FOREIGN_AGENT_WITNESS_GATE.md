# R1C — Foreign Agent Witness Gate

## Purpose

The next JANUS Machine Market promotion is **not payment** and **not autonomous purchase**.

The next admissible evidence is one real external machine-discovery/request roundtrip through the same bounded `JANUS.SEARCH` zero-price contour, followed by an immutable receipt on `janus/market-state`.

```text
EXTERNAL MACHINE CLIENT
        ↓
DISCOVERS MARKET
        ↓
GITHUB ISSUE INGRESS
        ↓
INDEPENDENCE GATE
        ↓
JANUS.SEARCH · PRICE 0
        ↓
EXISTING R1 BOUNDED RUNTIME
        ↓
RESULT RECEIPT
        ↓
PERSISTENT FOREIGN WITNESS RECEIPT
```

## Promotion law

```text
OWNER SELF-REQUEST          != FOREIGN_AGENT_WITNESS
WORKFLOW_DISPATCH           != FOREIGN_AGENT_WITNESS
SYNTHETIC FIXTURE           != FOREIGN_AGENT_WITNESS
PAYMENT                     != FOREIGN_AGENT_WITNESS
EXTERNAL PRINCIPAL + REAL REQUEST + PERSISTENT RECEIPT
                            => FOREIGN_AGENT_WITNESS
```

`FOREIGN_AGENT_WITNESS` stays **PENDING** until the persistent receipt exists.

The gate uses GitHub-observable independence signals. A qualifying requester must:

- have a GitHub login different from `Hawkar-usls`;
- have a GitHub numeric user ID different from the owner ID;
- not be a GitHub bot account;
- have `author_association` of `NONE`, `FIRST_TIMER`, or `FIRST_TIME_CONTRIBUTOR`;
- explicitly attest that the request is not controlled by the repository owner;
- explicitly identify the machine discovery surface used.

This is a strong platform-observable independence gate, not a claim that GitHub can prove the ultimate real-world controller of every account.

## Request format

Create a GitHub issue whose title begins:

```text
[JANUS FOREIGN MACHINE REQUEST]
```

The body must contain both machine blocks.

### 1. Bounded JANUS.SEARCH request

```text
<!-- JANUS_MACHINE_REQUEST_JSON
{
  "schema": "janus.machine_market.request.v1",
  "request_id": "external-client-generated-unique-id",
  "purchase_id": null,
  "sku": "JANUS.SEARCH",
  "input": {
    "query": "machine-readable research API provenance",
    "source_scope": "MARKET_CATALOG",
    "max_results": 5
  },
  "requested_output": {
    "format": "application/json"
  },
  "max_runtime_seconds": 10,
  "created_at": null
}
JANUS_MACHINE_REQUEST_JSON -->
```

### 2. Discovery witness claim

```text
<!-- JANUS_DISCOVERY_WITNESS_JSON
{
  "schema": "janus.machine_market.foreign_discovery_claim.v1",
  "discovery_surface": "GITHUB_PAGES",
  "discovered_url": "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/",
  "machine_client": true,
  "independent_from_owner": true
}
JANUS_DISCOVERY_WITNESS_JSON -->
```

Allowed discovery surfaces are frozen in `runtime/FOREIGN_AGENT_WITNESS_POLICY.json`.

## What a successful gate persists

A successful external request writes an immutable receipt to:

```text
janus/market-state
└── state/r1-foreign/receipts/faw-<sha256>.json
```

The receipt binds:

```text
GitHub repository identity
+ issue identity
+ requester login / numeric ID / association
+ discovery claim hash
+ request hash
+ purchase identity
+ purchase grant hash
+ execution identity
+ result hash
+ result receipt
```

A fresh checkout then replays the same request and must prove:

```text
same request_hash
same execution_id
same result_sha256
billable_execution_delta = 0
execution_count_for_purchase = 1
```

## Commercial state remains closed

Passing R1C does **not** enable payment.

```text
GENERAL PAYMENT API      CLOSED
x402                     PLANNED_NOT_ACTIVE
AUTONOMOUS PURCHASE      NOT DECLARED
JANUS.INFERENCE          CLOSED_TARGET_EXECUTION_WITNESS_PENDING
JANUS.COMPUTE            CLOSED_TARGET_EXECUTION_WITNESS_PENDING
```

The foreign-agent witness proves that an independently originated machine request can discover JANUS, enter the bounded contour, receive a result, and leave a persistent verifiable trace. It does not prove production inference/compute authority.

## Core law

> **DISCOVERY != PURCHASE != EXECUTION AUTHORITY.**

> **FOREIGN_AGENT_WITNESS requires a foreign requester, not a self-generated simulation of one.**
