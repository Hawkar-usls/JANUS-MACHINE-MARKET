# Security Policy

JANUS MACHINE MARKET is a discovery and commercial-control surface. It is not permission for arbitrary execution inside JANUS.

## Security invariants

```text
PAYMENT != EXECUTION AUTHORITY
PURCHASE != SHELL ACCESS
PURCHASE != SECRET ACCESS
PURCHASE != UNBOUNDED NETWORK ACCESS
PURCHASE != CLAIM AUTHORITY
```

Future executable SKUs must be allowlisted, bounded, policy-checked and independently granted by the governing JANUS execution authority.

## Current state

- General transaction API: **not established**.
- x402 purchase endpoint: **not active**.
- `JANUS.INFERENCE`: **closed** pending a persistent end-to-end target execution witness.
- `JANUS.COMPUTE`: **closed** pending the same witness and additional workload/sandbox policy.
- `HELIOS.PILOT`: governed by its canonical HELIOS authority, not by this repository.

## Secrets

Do not commit wallet private keys, seed phrases, exchange credentials, API secrets, authentication tokens or private buyer material to this repository.

Public receiving addresses may be declared as policy data, but a public address is not a universal checkout endpoint.

## Third-party content

Archive or dataset discovery does not grant redistribution rights. A source must be handled under its own license and access policy.

## Reporting

For security-sensitive findings, contact the repository owner through the public GitHub identity rather than publishing exploitable secrets in an issue.
