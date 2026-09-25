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

## MCP 2026-07-28 security boundary

The future MCP surface is pinned to revision `2026-07-28`, but no live MCP server is currently claimed.

- Do not derive identity, authorization or FOREIGN_AGENT_WITNESS status from `clientInfo`, `serverInfo`, connection reuse, or any removed session header.
- Cross-request state must use explicit application handles; transport/session affinity is not authority.
- A future server must implement `server/discover`, but discovery metadata remains self-reported and is not a security principal.
- If HTTP authorization is enabled, use the MCP authorization profile: protected-resource metadata, authorization-server discovery, issuer-bound credentials, and RFC 9207 issuer validation.
- Dynamic Client Registration is compatibility-only for the target revision; new design should prefer Client ID Metadata Documents.
- MCP Registry listing is discovery evidence only. It does not prove execution, purchase authority, or an independent external principal.

## Secrets

Do not commit wallet private keys, seed phrases, exchange credentials, API secrets, authentication tokens or private buyer material to this repository.

Public receiving addresses may be declared as policy data, but a public address is not a universal checkout endpoint.

## Third-party content

Archive or dataset discovery does not grant redistribution rights. A source must be handled under its own license and access policy.

## Reporting

For security-sensitive findings, contact the repository owner through the public GitHub identity rather than publishing exploitable secrets in an issue.
