# JANUS x402 Buyer Pilot

JANUS now distinguishes two different payment directions:

```text
JANUS AS SELLER != JANUS AS BUYER
```

Seller-side paid JANUS services remain gated by the canonical Market commerce and foreign-agent witness rules.

Buyer-side external x402 calls may run under the independent `X402_BUYER_POLICY.json` when explicitly authorized and within its hard spend boundary.

## First live target

The initial pilot is deliberately frozen to one external resource:

```text
provider: MACH Base
method: GET
resource: https://api.mach.gallery/api/base/block-number
network: Base mainnet (eip155:8453)
asset: native Circle USDC
contract: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
maximum payment: 0.005 USDC
maximum rolling 24h spend: 0.005 USDC
```

No other host, route, asset, network or price is admitted by this pilot.

## Runtime

The live client is:

```text
runtime/x402_buyer_call.mjs
```

It uses the official x402 v2 fetch client through a CDP-managed signer with explicit spend controls.

The repository never stores a wallet private key.

Required GitHub Actions secrets:

```text
CDP_API_KEY_ID
CDP_API_KEY_SECRET
CDP_WALLET_SECRET
```

The managed payer wallet must hold enough native USDC on Base mainnet for the authorized call.

## Running the pilot

Use the GitHub Actions workflow:

```text
JANUS x402 Buyer — MACH Base Pilot
```

It is `workflow_dispatch` only. The operator must enter exactly:

```text
PAY_0_005_USDC_TO_MACH
```

The workflow then permits one bounded payment attempt against the frozen MACH resource.

## Receipt

Each run writes:

```text
artifacts/x402-buyer/latest.json
```

and uploads it as the workflow artifact.

The receipt binds the provider/resource, payer address, Base network, USDC asset, authorized maximum, HTTP status, response digest and payment-response metadata digest.

## Fail-closed rules

```text
EXTERNAL_BUYER_SPEND_ENABLED != SELLER_MONEY_ENABLED
BUYER_PAYMENT != FOREIGN_AGENT_WITNESS
BUYER_PAYMENT != JANUS.SEARCH PURCHASE AUTHORITY
BUYER_PAYMENT != COMMAND AUTHORITY
BUYER_PAYMENT != EXECUTION AUTHORITY
```

If a signed/payment attempt ends ambiguously, do not automatically retry. First determine whether settlement occurred.

This pilot MUST NOT modify `FOREIGN_AGENT_WITNESS.json` or promote paid JANUS selling.
