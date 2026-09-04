---
name: JANUS Paid Search
about: Request one paid bounded JANUS.SEARCH turn
labels: ''
assignees: ''
title: '[JANUS PAID SEARCH] '
---

> Do **not** send funds just because this issue exists. Payment is valid only after the marketplace posts a live invoice for this exact issue.

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

After payment settlement, the issue will show the sealed purchase ID, queue level, current queue position and an estimated wait range. Queue position/ETA are estimates, not delivery guarantees, because later higher-level requests may overtake requests that have not started. Aging prevents indefinite starvation of lower levels without charging them again.

By submitting this request, you are asking for one bounded read-only JANUS.SEARCH turn under `docs/PAID_SEARCH_TERMS.md`. Payment never grants command, shell, secret, repository-write, or external-effect authority.
