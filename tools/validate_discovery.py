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
global_a2a = load_json("discovery/GLOBAL_A2A_REGISTRY.json")
mcp = load_json("discovery/MCP_PUBLICATION.json")
x402 = load_json("discovery/X402_BAZAAR_PUBLICATION.json")
openapi = load_json("discovery/OPENAPI_PUBLICATION.json")
witness_policy = load_json("runtime/FOREIGN_AGENT_WITNESS_POLICY.json")

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

# Protocol publication remains fail-closed. Registry discovery is a separate
# address-book surface and must never be confused with a callable A2A server.
require(a2a.get("current_publication_allowed") is False, "A2A_AGENT_CARD_PUBLICATION_MUST_FAIL_CLOSED")
require(a2a.get("a2a_runtime_live") is False, "A2A_RUNTIME_MUST_REMAIN_FALSE")
require(a2a.get("canonical_agent_card_published") is False, "A2A_AGENT_CARD_MUST_REMAIN_UNPUBLISHED")
require(a2a.get("status") == "GLOBAL_REGISTRY_DISCOVERY_READY_AGENT_CARD_RUNTIME_GATED", "A2A_STATUS_DRIFT")
require((a2a.get("global_registry_discovery") or {}).get("registry_listing_allowed_now") is True, "A2A_REGISTRY_LISTING_NOT_ALLOWED")
require((a2a.get("global_registry_discovery") or {}).get("listing_is_a2a_runtime_witness") is False, "REGISTRY_LISTING_MUST_NOT_PROVE_A2A_RUNTIME")
require((a2a.get("agent_card_runtime_contract") or {}).get("github_issue_ingress_may_be_advertised_as_a2a_interface") is False, "GITHUB_ISSUES_MUST_NOT_MASQUERADE_AS_A2A")
require((a2a.get("agent_card_runtime_contract") or {}).get("github_pages_may_be_advertised_as_a2a_interface") is False, "GITHUB_PAGES_MUST_NOT_MASQUERADE_AS_A2A")

require(global_a2a.get("status") == "SUBMISSION_READY_NOT_YET_INDEPENDENTLY_VERIFIED_AS_LISTED", "GLOBAL_A2A_REGISTRY_STATUS_DRIFT")
truth = global_a2a.get("current_truth") or {}
require(truth.get("registry_listing_allowed_now") is True, "GLOBAL_A2A_REGISTRY_LISTING_NOT_READY")
require(truth.get("a2a_runtime_live") is False, "GLOBAL_A2A_REGISTRY_FALSE_RUNTIME_CLAIM")
require(truth.get("canonical_a2a_agent_card_published") is False, "GLOBAL_A2A_REGISTRY_FALSE_AGENT_CARD_CLAIM")
require(truth.get("current_callable_service_is_a2a") is False, "CURRENT_GITHUB_INGRESS_MUST_NOT_BE_A2A")
submission = global_a2a.get("janus_submission") or {}
require(submission.get("input") == "https://github.com/Hawkar-usls/JANUS-MACHINE-MARKET", "GLOBAL_A2A_SUBMISSION_TARGET_DRIFT")
require(submission.get("listing_verified") is False, "GLOBAL_A2A_LISTING_MUST_NOT_BE_PRETENDED_VERIFIED")
require(submission.get("submission_receipt_present") is False, "GLOBAL_A2A_SUBMISSION_RECEIPT_MUST_NOT_BE_INVENTED")

for name, record in {
    "MCP": mcp,
    "X402": x402,
    "OPENAPI": openapi,
}.items():
    require(record.get("current_publication_allowed") is False, f"{name}_PUBLICATION_MUST_FAIL_CLOSED")
    require("PREPARED" in str(record.get("status", "")), f"{name}_PREPUBLICATION_STATUS_DRIFT")

allowed_surfaces = set((witness_policy.get("required_discovery_claim") or {}).get("allowed_surfaces") or [])
require("GLOBAL_A2A_REGISTRY" in allowed_surfaces, "GLOBAL_A2A_NOT_ALLOWED_AS_FOREIGN_DISCOVERY_SURFACE")
semantics = (witness_policy.get("discovery_surface_semantics") or {}).get("GLOBAL_A2A_REGISTRY") or {}
require(semantics.get("acceptable_as_frozen_discovery_source") is True, "GLOBAL_A2A_DISCOVERY_SEMANTICS_MISSING")
require(semantics.get("proves_a2a_runtime") is False, "GLOBAL_A2A_DISCOVERY_MUST_NOT_PROVE_RUNTIME")
require(semantics.get("proves_execution") is False, "GLOBAL_A2A_DISCOVERY_MUST_NOT_PROVE_EXECUTION")
require(semantics.get("proves_purchase_authority") is False, "GLOBAL_A2A_DISCOVERY_MUST_NOT_PROVE_PURCHASE")
require((witness_policy.get("promotion_law") or {}).get("registry_listing_alone_can_promote") is False, "REGISTRY_LISTING_MUST_NOT_PROMOTE_COMMERCE")

surface_by_id = {row.get("id"): row for row in beacon.get("discovery_surfaces", [])}
require("GLOBAL_A2A_REGISTRY" in surface_by_id, "BEACON_GLOBAL_A2A_SURFACE_MISSING")
require(surface_by_id["GLOBAL_A2A_REGISTRY"].get("foreign_discovery_claim_allowed") is True, "BEACON_GLOBAL_A2A_WITNESS_SURFACE_FALSE")
require(surface_by_id["GLOBAL_A2A_REGISTRY"].get("proves_a2a_runtime") is False, "BEACON_GLOBAL_A2A_FALSE_RUNTIME_CLAIM")
require(surface_by_id["A2A_AGENT_CARD"].get("current_agent_card_published") is False, "BEACON_AGENT_CARD_FALSE_PUBLICATION")

for law in [
    "DISCOVERABLE_DOES_NOT_MEAN_PURCHASABLE",
    "PAYMENT_IS_EVIDENCE_NOT_AUTHORITY",
    "UNSOLICITED_PAYMENT_GRANTS_NOTHING",
    "PURCHASE_GRANT_DOES_NOT_BYPASS_EXECUTION_POLICY",
    "GLOBAL_A2A_REGISTRY_LISTING_DOES_NOT_PROVE_A2A_RUNTIME",
    "A2A_AGENT_CARD_REQUIRES_REAL_SUPPORTED_INTERFACE",
]:
    require(law in beacon.get("truth_boundary", []), f"MISSING_DISCOVERY_TRUTH_LAW:{law}")

require(
    "ZERO_PRICE_SHADOW_ROUNDTRIP_PASS_BEFORE_MONEY" in x402.get("publication_gates", []),
    "X402_MISSING_ZERO_PRICE_SHADOW_GATE",
)
require(
    beacon.get("next_activation_gate") == "FIRST_REAL_EXTERNAL_MACHINE_PUBLIC_SEARCH_PERSISTENT_HOME_RECEIPT",
    "NEXT_ACTIVATION_GATE_DRIFT",
)

# Until a real A2A/MCP/OpenAPI runtime exists, no live protocol descriptor may
# appear just because JANUS became registry-discoverable.
for path in [
    ".well-known/agent-card.json",
    "server.json",
    "openapi.json",
]:
    require(not (ROOT / path).exists(), f"PREMATURE_LIVE_DISCOVERY_DESCRIPTOR:{path}")

print("JANUS_MACHINE_MARKET_DISCOVERY_INTEGRITY_PASS")
print("DISCOVERY_ACTIVE=TRUE")
print("GLOBAL_A2A_REGISTRY_DISCOVERY=SUBMISSION_READY_NOT_VERIFIED_LISTED")
print("FOREIGN_DISCOVERY_SURFACE_GLOBAL_A2A_REGISTRY=ALLOWED")
print("A2A_RUNTIME_ACTIVE=FALSE")
print("A2A_AGENT_CARD_PUBLISHED=FALSE")
print("REGISTRY_LISTING_PROVES_A2A_RUNTIME=FALSE")
print("TRANSACTION_API_ACTIVE=FALSE")
print("MCP_PUBLISHED=FALSE")
print("X402_BAZAAR_REGISTERED=FALSE")
