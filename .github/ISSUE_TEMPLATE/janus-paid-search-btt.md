---
name: JANUS Paid Search — BTT / TRON Live Checkout
about: Buy one bounded JANUS.SEARCH task with an exact BitTorrent Token TRC-20 invoice
title: '[JANUS PAID SEARCH BTT] '
labels: ''
assignees: ''
---

> **BTT / TRON EXACT-INVOICE CHECKOUT.** Do **not** send BTT before JANUS posts the exact invoice for this issue.

Choose one queue level and replace `YOUR QUERY HERE`. Keep the marker intact.

- `1` — STANDARD · 1.00×
- `2` — PRIORITY · 1.50×
- `3` — EXPRESS · 2.25×
- `4` — PRIME · 3.50×
- `5` — GATE · 5.00×

<!-- JANUS_PAID_SEARCH_BTT_JSON
{"schema":"janus.machine_market.buyer_query_shadow_request.v1","queue_level":1,"message_text":"YOUR QUERY HERE"}
JANUS_PAID_SEARCH_BTT_JSON -->

JANUS freezes the normal USDT reference price, applies the declared **50% BTT-route discount**, obtains a fresh public Binance **`BTTCUSDT`** order-book observation, rounds **up** to the exact 18-decimal BTT atomic amount, reserves queue capacity, and posts the resulting invoice here.

`BTTC` is Binance's exchange ticker for the post-redenomination **BitTorrent Token**. The payment asset here is that BitTorrent Token (`BTT`) as TRC-20 on TRON Mainnet, token contract `TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4`. This is not BTTOLD.

The receiver and exact amount are repeated in the issue invoice. Do not infer an order from the published wallet alone.

After the exact transfer is solidified, post a new comment using the marker JANUS gives you, containing the TRON `txid` and (if necessary) the exact TRC-20 `event_index`.

Payment settlement creates a queue entry; it does not grant command, shell, secret, repository-write, external-effect, or unrestricted execution authority.
