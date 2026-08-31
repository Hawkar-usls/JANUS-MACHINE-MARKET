# Adaptive pricing

JANUS Machine Market prices are designed to move gradually with observed demand and public market benchmarks.

- An already issued quote never changes.
- Underused available services can become cheaper and receive more discovery promotion.
- Highly demanded services can rise gradually, but automated raises are capped per rebalance and blocked when benchmark data are stale, service failure is elevated, or fulfillment debt is open.
- For comparable services the governor targets a price below the lowest verified published comparable market rate. If JANUS cannot stay below the competitive ceiling without crossing a configured cost floor, the service must hold rather than silently sell at a known loss.
- A low price never turns a closed SKU into an available one.

The dynamic price and discovery heartbeat are published separately from source code on the `janus/market-live` branch. This keeps dynamic state out of the canonical code branch while giving machine buyers a stable fresh endpoint.
