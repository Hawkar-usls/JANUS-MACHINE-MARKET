#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str):
    p = ROOT / path
    if not p.is_file():
        raise SystemExit(f"MISSING_REQUIRED_DISCOVERY_FILE:{path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"INVALID_JSON:{path}:{exc}") from exc


def require(condition: bool, code: str):
    if not condition:
        raise SystemExit(code)


beacon = load_json("BEACON.json")
agent = load_json("AGENT_MARKET.json")
catalog = load_json("CATALOG.json")
pointer = load_json(".well-known/agent-market.json")
a2a = load_json("discovery/A2A_PUBLICATION.json")
mcp = load_json("discovery/MCP_PUBLICATION.json")
x402 = load_json("discovery/X402_BAZAAR_PUBLICATION.json")
openapi = load_json("discovery/OPENAPI_PUBLICATION.json")

require(beacon.get("status") == "DISCOVERY_ACTIVE_TRANSACTION_API_NOT_ESTABLISHED", "BEACON_STATUS_DRIFT")
require(agent.get("transaction_api", {}).get("status") == "NOT_ESTABLISHED", "AGENT_TRANSACTION_STATUS_DRIFT")
require(agent.get("transaction_api", {}).get("endpoint") is None, "AGENT_TRANSACTION_ENDPOINT_MUST_BE_NULL")
require(pointer.get("transaction_api_status") == "NOT_ESTABLISHED", "WELL_KNOWN_TRANSACTION_STATUS_DRIFT")
require(agent.get("x402", {}).get("status") == "PLANNED_NOT_ACTIVE", "X402_MUST_REMAIN_INACTIVE_BEFORE_R1")

products = {row.get("sku"): row for row in catalog.get("products", [])}
for sku in beacon.get("priority_skus", []):
    require(sku in products, f"BEACON_PRIORITY_SKU_NOT_IN_CATALOG:{sku}")
    require(products[sku].get("machine_discovery") is True, f"PRIORITY_SKU_NOT_DISCOVERABLE:{sku}")

for sku in beacon.get("closed_until_target_execution_witness", []):
    require(sku in products, f"CLOSED_SKU_NOT_IN_CATALOG:{sku}")
    require(products[sku].get("machine_purchase") is False, f"CLOSED_SKU_MACHINE_PURCHASE_MUST_BE_FALSE:{sku}")
    require(products[sku].get("status") == "CLOSED_TARGET_EXECUTION_WITNESS_PENDING", f"CLOSED_SKU_STATUS_DRIFT:{sku}")

records = {
    "A2A": a2a,
    "MCP": mcp,
    "X402": x402,
    "OPENAPI": openapi,
}
for name, record in records.items():
    require(record.get("current_publication_allowed") is False, f"{name}_PUBLICATION_MUST_FAIL_CLOSED")
    require("PREPARED" in str(record.get("status", "")), f"{name}_PREPUBLICATION_STATUS_DRIFT")

for law in [
    "DISCOVERABLE_DOES_NOT_MEAN_PURCHASABLE",
    "PAYMENT_IS_EVIDENCE_NOT_AUTHORITY",
    "UNSOLICITED_PAYMENT_GRANTS_NOTHING",
    "PURCHASE_GRANT_DOES_NOT_BYPASS_EXECUTION_POLICY",
]:
    require(law in beacon.get("truth_boundary", []), f"MISSING_DISCOVERY_TRUTH_LAW:{law}")

require(
    "ZERO_PRICE_SHADOW_ROUNDTRIP_PASS_BEFORE_MONEY" in x402.get("publication_gates", []),
    "X402_MISSING_ZERO_PRICE_SHADOW_GATE",
)
require(
    beacon.get("next_activation_gate") == "R1_ZERO_PRICE_SHADOW_SEARCH_ROUNDTRIP",
    "NEXT_ACTIVATION_GATE_DRIFT",
)

# While no runtime exists, do not publish standard live descriptors that would
# cause third-party agents to believe a callable endpoint exists.
if agent.get("transaction_api", {}).get("status") == "NOT_ESTABLISHED":
    forbidden_live_claims = [
        ".well-known/agent-card.json",
        "server.json",
        "openapi.json",
    ]
    for path in forbidden_live_claims:
        require(not (ROOT / path).exists(), f"PREMATURE_LIVE_DISCOVERY_DESCRIPTOR:{path}")

print("JANUS_MACHINE_MARKET_DISCOVERY_INTEGRITY_PASS")
print("DISCOVERY_ACTIVE=TRUE")
print("TRANSACTION_API_ACTIVE=FALSE")
print("A2A_PUBLISHED=FALSE")
print("MCP_PUBLISHED=FALSE")
print("X402_BAZAAR_REGISTERED=FALSE")
