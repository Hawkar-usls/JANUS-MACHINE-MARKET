#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def require(cond: bool, code: str) -> None:
    if not cond:
        raise SystemExit(code)


def main() -> int:
    plane = load("BUYER_QUERY_PLANE.json")
    grant_schema = load("schemas/grant.schema.json")
    query_schema = load("schemas/buyer-query.schema.json")
    receipt_schema = load("schemas/buyer-query-receipt.schema.json")
    search = load("products/JANUS.SEARCH.json")
    witness = load("FOREIGN_AGENT_WITNESS.json")
    readiness = load("COMMERCE_READINESS.json")

    gates = plane.get("current_gates") or {}
    seller_live = readiness.get("seller_commerce_authorized") is True and readiness.get("money_enabled") is True
    require(seller_live, "BUYER_QUERY_SELLER_COMMERCE_NOT_LIVE")
    require(plane.get("status") == "ZERO_PRICE_AND_PAID_SEARCH_LIVE_FIRST_PAID_DELIVERY_PENDING", "BUYER_QUERY_LIVE_STATUS_INVALID")
    require(gates.get("seller_commerce_authorized") is True, "BUYER_QUERY_SELLER_AUTHORITY_MISSING")
    require(gates.get("payment_endpoint") == "LIVE_JANUS_SEARCH_ONLY", "BUYER_QUERY_LIVE_PAYMENT_ENDPOINT_INVALID")
    require(gates.get("foreign_buyer_query_witness") in ("PENDING", "PASS_PERSISTENT_HOME_EXTERNAL_MACHINE"), "BUYER_QUERY_FOREIGN_WITNESS_STATE_INVALID")
    require(gates.get("foreign_buyer_query_witness_is_seller_prerequisite") is False, "BUYER_QUERY_WITNESS_MUST_NOT_GATE_SELLER")
    require(gates.get("live_publication_allowed") is True, "BUYER_QUERY_LIVE_PUBLICATION_NOT_ALLOWED")
    require(readiness.get("autonomous_purchase_declared") is True, "BUYER_QUERY_LIVE_COMMERCE_SWITCH_INVALID")
    require(search.get("machine_purchase") is True, "BUYER_QUERY_LIVE_SEARCH_MACHINE_PURCHASE_FALSE")
    require((search.get("live_gate") or {}).get("checkout_live") is True, "BUYER_QUERY_LIVE_CHECKOUT_FALSE")
    require((search.get("live_gate") or {}).get("paid_queue_live") is True, "BUYER_QUERY_LIVE_PAID_QUEUE_FALSE")
    require((search.get("live_gate") or {}).get("foreign_agent_witness_is_seller_prerequisite") is False, "BUYER_QUERY_PRODUCT_WITNESS_GATE_INVALID")
    require(search.get("post_purchase_query",{}).get("status") == "PAID_QUEUE_AND_HOME_ROUTE_LIVE_FIRST_PAID_DELIVERY_PENDING", "BUYER_QUERY_LIVE_HOME_STATUS_INVALID")
    require(plane.get("next_gate") == "FIRST_REAL_PAID_SEARCH_SETTLEMENT_QUEUE_DISPATCH_PERSISTENT_HOME_RESULT_RECEIPT", "BUYER_QUERY_LIVE_NEXT_GATE_INVALID")
    require(gates.get("purchase_grant_paid_witness") == "PENDING_FIRST_REAL_PAID_SETTLEMENT", "PAID_DELIVERY_WITNESS_STATE_INVALID")
    require(gates.get("activator_buyer_query_binding") == "PASS_DUAL_MODE_ZERO_AND_PAID", "ACTIVATOR_PAID_BINDING_NOT_PROVEN")
    require(gates.get("physarius_market_to_home_vessel") == "PASS_DUAL_MODE_PACKET_CONTRACT", "PHYSARIUS_PAID_VESSEL_NOT_PROVEN")

    if witness.get("foreign_agent_witness") is True:
        require(witness.get("promotion_authority") == "PERSISTENT_HOME_RECEIPT_VERIFIED", "BUYER_QUERY_WITNESS_PROMOTION_AUTHORITY_INVALID")
    else:
        require(witness.get("status") == "PENDING_REAL_EXTERNAL_PERSISTENT_HOME_REQUEST", "BUYER_QUERY_PENDING_WITNESS_STATUS_INVALID")

    laws = set(plane.get("laws") or [])
    required_laws = {
        "PAYMENT != COMMAND",
        "PAYMENT != EXECUTION_AUTHORITY",
        "BUYER_QUERY != COMMAND",
        "JANUS_RESPONSE != WORLD_TRUTH",
        "MODEL_OUTPUT != EVIDENCE",
        "EXACT_RETRY != SECOND_BILLABLE_EXECUTION",
    }
    require(required_laws.issubset(laws), "BUYER_QUERY_CORE_LAWS_MISSING")

    props = (grant_schema.get("properties") or {})
    entitlement = props.get("buyer_query_entitlement") or {}
    require(entitlement, "PURCHASE_GRANT_QUERY_ENTITLEMENT_SCHEMA_MISSING")
    eprops = entitlement.get("properties") or {}
    require(eprops.get("read_only_conversation", {}).get("const") is True, "QUERY_ENTITLEMENT_NOT_READ_ONLY")
    require(eprops.get("external_effect_authorized", {}).get("const") is False, "QUERY_ENTITLEMENT_EFFECT_AUTHORITY_FORBIDDEN")
    require(props.get("execution_authority_granted", {}).get("const") is False, "PURCHASE_GRANT_MUST_NOT_GRANT_EXECUTION_AUTHORITY")

    require(query_schema.get("properties", {}).get("message_text"), "BUYER_QUERY_MESSAGE_TEXT_SCHEMA_MISSING")
    require(query_schema.get("properties", {}).get("query_hash"), "BUYER_QUERY_HASH_SCHEMA_MISSING")
    rprops = receipt_schema.get("properties") or {}
    require(rprops.get("execution_authority_granted", {}).get("const") is False, "BUYER_QUERY_RECEIPT_EXECUTION_AUTHORITY_FORBIDDEN")
    require(rprops.get("external_effect_authorized", {}).get("const") is False, "BUYER_QUERY_RECEIPT_EFFECT_AUTHORITY_FORBIDDEN")

    post = search.get("post_purchase_query") or {}
    require(post.get("enabled_only_by_explicit_purchase_grant_entitlement") is True, "QUERY_ENTITLEMENT_GATE_MISSING")
    require(post.get("query_is_command") is False, "QUERY_MUST_NOT_BECOME_COMMAND")
    require(post.get("payment_is_command") is False, "PAYMENT_MUST_NOT_BECOME_COMMAND")
    require(post.get("purchase_grant_is_execution_authority") is False, "PURCHASE_GRANT_MUST_NOT_BECOME_EXECUTION_AUTHORITY")
    require(post.get("external_effect_authorized") is False, "QUERY_EXTERNAL_EFFECTS_FORBIDDEN")
    require(post.get("execution_starts_only_after_queue_dispatch") is True, "PAID_QUEUE_DISPATCH_GATE_MISSING")

    print("JANUS_BUYER_QUERY_PLANE_DUAL_STATE_INTEGRITY=PASS")
    print("PAID_QUEUE_AND_HOME_BUYER_QUERY_BINDING=PASS")
    print("PURCHASE_GRANT_QUERY_ENTITLEMENT_BOUNDARY=PASS")
    print("BUYER_QUERY_COMMAND_AUTHORITY=FALSE")
    print("BUYER_QUERY_EXTERNAL_EFFECT_AUTHORITY=FALSE")
    print("LIVE_PAID_CHECKOUT=TRUE_SELLER_AUTHORIZED")
    print("FOREIGN_AGENT_WITNESS=" + ("TRUE" if witness.get("foreign_agent_witness") else "FALSE_PENDING_REAL_EVIDENCE"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
