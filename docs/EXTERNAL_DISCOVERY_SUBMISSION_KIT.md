# JANUS MACHINE MARKET — External Discovery Submission Kit

Recorded: 2026-09-28

This kit exists to increase independent external discovery **without inflating runtime claims**.

## Canonical live capability

`JANUS.SEARCH` has a live GitHub-authenticated ingress through GitHub Issues. The first new bounded SEARCH order per external GitHub principal is zero-price. Subsequent `JANUS.SEARCH` has bounded exact-invoice checkout through the currently declared seller rails.

Canonical OpenAPI descriptor:

`https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/discovery/GITHUB_ISSUES_INGRESS.openapi.json`

Canonical discovery index:

`https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/apis.json`

Canonical docs:

`https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/`

Repository:

`https://github.com/Hawkar-usls/JANUS-MACHINE-MARKET`

## Truth boundary

Do not describe JANUS as having any of the following until their separate runtime gates are green:

- general JANUS HTTP transaction API
- live MCP server
- live A2A runtime / callable Agent Card
- live x402 seller resource

The deployed GitHub Issues OpenAPI is a real machine-readable contract, but:

`GITHUB_ISSUES_OPENAPI != GENERAL_TRANSACTION_API`

`DISCOVERY != EXECUTION_WITNESS`

`SELLER_COMMERCE_AUTHORIZED != FOREIGN_AGENT_WITNESS`

## APIs.io

Status: `LISTED`.

A re-profile was requested after paid `JANUS.SEARCH` became live. Source of truth is `apis.json` / `.well-known/apis.json`.

## APIs.guru OpenAPI Directory

Status: `SUBMISSION_READY_EXTERNAL_WRITE_REQUIRED`.

Suggested submission fields:

- Definition URL: `https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/discovery/GITHUB_ISSUES_INGRESS.openapi.json`
- Format: `OpenAPI`
- Official: `Yes`
- API name: `JANUS Machine Market — JANUS.SEARCH GitHub Issues Ingress`
- Category: `data` or `search`, whichever the directory currently accepts

Suggested description:

> Live GitHub-authenticated machine ingress for bounded provenance-aware JANUS.SEARCH requests. External callers create a request through the public GitHub Issues REST API using their own GitHub credentials, and the reconciled result returns on the same issue surface. The first SEARCH order per external GitHub principal is zero-price. This descriptor covers the GitHub Issues transport only; it does not claim a general JANUS transaction API, live MCP server, live A2A runtime, or live x402 seller resource.

The owner GitHub App currently cannot open an issue in the external APIs-guru repository, so this submission requires an external write-capable browser/account surface.

## Postman API Network

Status: `PUBLICATION_READY_ACCOUNT_REQUIRED`.

Import this repository artifact into a public Postman workspace:

`discovery/postman/JANUS_SEARCH.postman_collection.json`

The collection contains no token. The external caller supplies its own `github_token` variable. Publishing the collection does not constitute an execution witness.

## RapidAPI Hub

Status: `EVALUATE_PROVIDER_ACCOUNT_PATH`.

RapidAPI supports OpenAPI import through its provider surface, but JANUS must not be represented as a direct general-purpose HTTP transaction API when the actual live transport is GitHub Issues. Publish only if the provider listing can faithfully preserve that transport/authentication model.

## A2A / MCP / x402

Do not publish callable runtime descriptors merely to gain visibility.

- A2A Agent Card: runtime-gated.
- Official MCP Registry/server manifest: runtime-gated.
- x402/Bazaar seller resource: HTTP 402 seller-resource gated.

Discovery should increase the probability of an independent request, not manufacture evidence.

## Conversion target

The acquisition target remains:

`INDEPENDENT EXTERNAL PRINCIPAL`
`-> public JANUS.SEARCH`
`-> Market acceptance`
`-> persistent HOME processing`
`-> HOME response`
`-> Market reconcile`
`-> durable state/r1-foreign-home/FIRST.json`

Only that evidence path may promote `foreign_agent_witness` under the canonical policy.
