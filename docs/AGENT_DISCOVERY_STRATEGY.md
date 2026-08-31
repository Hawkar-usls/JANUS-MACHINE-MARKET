# JANUS MACHINE MARKET — Agent Discovery Strategy

## Goal

Make JANUS products easy for autonomous buyer agents to find, understand, compare and eventually purchase without overstating runtime capabilities that do not yet exist.

The discovery fabric deliberately separates **being findable** from **being callable** and **being purchasable**.

```text
DISCOVERY
  != PURCHASE AUTHORITY
  != EXECUTION AUTHORITY
  != EXECUTION WITNESS
```

## R0.5 — passive discovery now

Publish machine-readable descriptions in GitHub immediately:

- `BEACON.json` — canonical cross-protocol discovery status.
- `AGENT_MARKET.json` — JANUS-native agent manifest.
- `.well-known/agent-market.json` — compact JANUS-native discovery pointer.
- `CATALOG.json` — SKU catalog.
- `COMMERCIAL.json` — commercial boundary.
- `llms.txt` — concise model/crawler-oriented index.
- `products/*.json` — per-SKU contracts.
- `schemas/*.json` — input/output/grant/receipt contracts.

This layer can be indexed by GitHub search, code crawlers, LLM tooling and custom agent crawlers without a live transaction server.

## R1 — live search shadow endpoint

The first runtime should be `JANUS.SEARCH` in **zero-price shadow mode**.

Required roundtrip:

```text
agent
  -> request
  -> request_hash
  -> zero-price quote
  -> purchase_id
  -> idempotent PURCHASE_GRANT
  -> bounded JANUS search request
  -> result
  -> RESULT_RECEIPT
  -> replay of the same purchase_id returns the same commercial execution identity
```

No real payment should be enabled until this contour is observed end to end with persistent receipts.

## R2 — standards publication

### A2A

A2A standardizes discovery through an Agent Card served at:

`https://{service-origin}/.well-known/agent-card.json`

JANUS should publish that card only after a real HTTPS A2A endpoint exists. The first public skills should map to already-safe DATA/SEARCH SKUs. Do not advertise INFERENCE or COMPUTE as executable while their target-execution witness gate remains open.

### MCP

Once a real MCP server exists, expose bounded market tools such as:

- `janus_search`
- `janus_dataset_scout`
- `janus_evidence_pack`
- `janus_repo_audit`

Then publish a current `server.json` through the MCP Registry tooling. The registry manifest must resolve to a real server; a speculative manifest is forbidden.

### x402 Bazaar

For paid machine-to-machine access, add x402 v2 to the live HTTPS resource and include Bazaar discovery metadata. The Bazaar is valuable because buyer agents can query discoverable paid resources instead of knowing JANUS in advance.

The first x402 resource should be `JANUS.SEARCH`, after the zero-price shadow contour is green. Use an explicit payment identifier / purchase identifier and preserve the JANUS idempotency rule:

```text
1 purchase_id + 1 request_hash => <= 1 billable execution
```

Static Bazaar-looking JSON in GitHub does not itself make a service discoverable in a facilitator catalog. Registration must be observed against a live facilitator/discovery endpoint.

### OpenAPI

Publish OpenAPI only when the documented HTTP routes exist. The document should describe deployed behavior, not the roadmap.

## R3 — active distribution

After the live endpoint exists, distribute the same canonical product facts to multiple discovery surfaces instead of maintaining divergent product descriptions manually.

Recommended publication targets:

1. JANUS-native beacon and catalog.
2. A2A Agent Card.
3. MCP Registry.
4. x402 Bazaar-capable facilitators.
5. OpenAPI consumers.
6. `llms.txt` at the public service origin.
7. GitHub repository search metadata and README.

Every projection should be generated from the same canonical SKU/catalog state where practical.

## GitHub attraction signals

Recommended repository description vocabulary:

`Machine-readable AI agent marketplace for research APIs, data discovery, evidence synthesis, x402, MCP and A2A agent commerce.`

Recommended GitHub topics:

`ai-agents`, `agent-commerce`, `agentic-commerce`, `x402`, `mcp`, `model-context-protocol`, `a2a`, `agent2agent`, `api-marketplace`, `machine-to-machine`, `paid-api`, `research-api`, `data-marketplace`, `autonomous-agents`.

Keep the most important searchable nouns in the first part of README and in machine-readable manifests. Agents searching for a capability are more likely to query phrases such as `research API`, `dataset discovery`, `MCP tool`, `x402 paid API`, or `A2A agent` than the internal JANUS organ name.

## Truth boundary

A discovery system becomes dangerous when metadata outruns reality. Therefore:

- Discoverable does not mean purchasable.
- Payment is evidence, not authority.
- Unsolicited payment grants nothing.
- Purchase grant does not bypass execution policy.
- Delivery does not prove execution.
- A standards descriptor is published only when its advertised endpoint exists.
- Closed SKUs remain visible for roadmap discovery but keep `machine_purchase=false`.

The CI validator in `tools/validate_discovery.py` enforces the pre-runtime form of these laws.
