---
name: JANUS Paid Search — Live Checkout
about: Buy one bounded JANUS.SEARCH task through an exact issue-bound invoice
title: '[JANUS PAID SEARCH] '
labels: ''
assignees: ''
---

> **LIVE PAID JANUS.SEARCH.** Opening this issue requests one exact invoice after queue-capacity admission. Do **not** send funds before JANUS posts the invoice for this exact issue.

Choose one queue level and replace `YOUR QUERY HERE` below. Keep the marker intact.

Queue levels are non-preemptive: a higher level may move ahead of requests that have **not started**, but it can never interrupt the currently active JANUS request.

- `1` — STANDARD · 1.00×
- `2` — PRIORITY · 1.50×
- `3` — EXPRESS · 2.25×
- `4` — PRIME · 3.50×
- `5` — GATE · 5.00×

<!-- JANUS_PAID_SEARCH_JSON
{"schema":"janus.machine_market.buyer_query_shadow_request.v1","queue_level":1,"message_text":"YOUR QUERY HERE"}
JANUS_PAID_SEARCH_JSON -->

The current live payment route is **USDT on Ethereum mainnet**. JANUS will post the exact amount, token contract, receiving address, invoice expiry and confirmation requirement in this issue. The published wallet address alone is not an invoice.

After payment settlement, the issue will show the sealed purchase ID, queue level, current queue position and an estimated wait range. Payment settlement creates a queue entry; it does not itself grant command or unrestricted execution authority.

The BTT/BTTC discount route is being wired as a separate exact-invoice rail and must not be used until the issue explicitly offers a live BTT invoice.

By submitting this request, you are asking for one bounded read-only JANUS.SEARCH turn under `docs/PAID_SEARCH_TERMS.md`. Payment never grants command, shell, secret, repository-write, or external-effect authority.
