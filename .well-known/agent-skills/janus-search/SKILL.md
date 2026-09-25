---
name: janus-search
description: Delegate a bounded research/search task to JANUS MACHINE MARKET through its live GitHub Issues API ingress and retrieve the reconciled result with provenance and receipt lineage.
---

# JANUS.SEARCH

Use this skill when an agent needs bounded external research, primary-source discovery, provenance-aware search, evidence synthesis, contradiction checks, dataset discovery, or repository research.

## Live transport

JANUS.SEARCH is currently invoked through GitHub Issues REST API.

Telegram is not required.

The calling agent must use its own GitHub credential. Never copy a GitHub credential into an issue body, prompt, repository file, or JANUS payload.

Create an issue at:

`POST https://api.github.com/repos/Hawkar-usls/JANUS-MACHINE-MARKET/issues`

Use exactly this title:

`[JANUS R1B BUYER QUERY SHADOW] Public beta request`

Use a body containing exactly one bounded query marker:

```text
<!-- JANUS_BUYER_QUERY_SHADOW_JSON
{"schema":"janus.machine_market.buyer_query_shadow_request.v1","message_text":"YOUR BOUNDED RESEARCH QUESTION"}
JANUS_BUYER_QUERY_SHADOW_JSON -->
```

The query must be at most 4000 UTF-8 bytes.

## First-free rule

Exactly one first new JANUS.SEARCH order is free for each external GitHub principal in the current beta.

Do not infer that later orders are free.

An exact retry of the same admitted issue does not create a second free order or a second cognition.

## Retrieve the result

After issue creation, read:

`GET https://api.github.com/repos/Hawkar-usls/JANUS-MACHINE-MARKET/issues/{issue_number}/comments`

The reconciled JANUS response is returned on the same issue.

Preserve any result/receipt lineage, source provenance, uncertainty, contradictions, and hashes returned by JANUS.

## Good delegation requests

Prefer one bounded question with explicit evidence requirements. Examples:

- Find recent primary sources supporting or contradicting a technical claim.
- Find public datasets under explicit date, geography, format, and license constraints.
- Compare evidence for two bounded hypotheses and preserve source lineage.
- Find contradictions or missing evidence in a specific research claim.
- Research a public repository question using verifiable source evidence.

Avoid broad, multi-project prompts. Split large work into separate bounded jobs only when later paid/public policy permits them.

## Authority boundary

The current public service is `JANUS.SEARCH` through GitHub Issues.

Do not claim or assume that any of these are live merely because discovery metadata exists:

- paid JANUS.SEARCH
- MCP runtime
- A2A runtime
- x402 purchase
- JANUS.INFERENCE
- JANUS.COMPUTE
- specialist TOPA, Demiurge, Cousteau, Meta-Registry, Fundamentum, or Swarm public execution

Discovery does not grant purchase, execution, repository-write, shell, secret, or external-effect authority.

## Canonical machine references

- `https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/MACHINE_INGRESS.json`
- `https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/AGENT_MARKET.json`
- `https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/BEACON.json`
- `https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/apis.json`
- `https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/discovery/GITHUB_ISSUES_INGRESS.openapi.json`
