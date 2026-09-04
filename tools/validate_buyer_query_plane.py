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
    live = witness.get("foreign_agent_witness") is True
    if live:
        require(plane.get("status") == "ZERO_PRICE_AND_PAID_SEARCH_LIVE_FIRST_PAID_DELIVERY_PENDING", "BUYER_QUERY_LIVE_STATUS_INVALID")
        require(gates.get("payment_endpoint") == "LIVE_JANUS_SEARCH_ONLY", "BUYER_QUERY_LIVE_PAYMENT_ENDPOINT_INVALID")
        require(gates.get("foreign_buyer_query_witness") == "PASS_PERSISTENT_HOME_EXTERNAL_MACHINE", "BUYER_QUERY_LIVE_FOREIGN_WITNESS_INVALID")
        require(gates.get("live_publication_allowed") is True, "BUYER_QUERY_LIVE_PUBLICATION_NOT_ALLOWED")
        require(bool(gates.get("foreign_witness_id")), "BUYER_QUERY_LIVE_WITNESS_ID_MISSING")
        require(readiness.get("money_enabled") is True and readiness.get("autonomous_purchase_declared") is True, "BUYER_QUERY_LIVE_COMMERCE_SWITCH_INVALID")
        require(search.get("machine_purchase") is True, "BUYER_QUERY_LIVE_SEARCH_MACHINE_PURCHASE_FALSE")
        require((search.get("live_gate") or {}).get("checkout_live") is True, "BUYER_QUERY_LIVE_CHECKOUT_FALSE")
        require((search.get("live_gate") or {}).get("witness_id") == gates.get("foreign_witness_id"), "BUYER_QUERY_LIVE_WITNESS_BINDING_MISMATCH")
        require(search.get("post_purchase_query",{}).get("status") == "PAID_HOME_ROUTE_LIVE_FIRST_PAID_DELIVERY_PENDING", "BUYER_QUERY_LIVE_HOME_STATUS_INVALID")
        require(plane.get("next_gate") == "FIRST_REAL_PAID_SEARCH_SETTLEMENT_PERSISTENT_HOME_RESULT_RECEIPT", "BUYER_QUERY_LIVE_NEXT_GATE_INVALID")
    else:
        require(plane.get("status") == "ZERO_PRICE_LIVE_PAID_HOME_ROUTE_ARMED_WITNESS_PENDING", "BUYER_QUERY_BLOCKED_STATUS_INVALID")
        require(gates.get("payment_endpoint") == "ARMED_GATE_CLOSED", "BUYER_QUERY_BLOCKED_PAYMENT_ENDPOINT_INVALID")
        require(gates.get("foreign_buyer_query_witness") == "PENDING", "BUYER_QUERY_BLOCKED_FOREIGN_WITNESS_INVALID")
        require(gates.get("live_publication_allowed") is False, "BUYER_QUERY_BLOCKED_PUBLICATION_MUST_BE_FALSE")
        require(readiness.get("money_enabled") is False and readiness.get("autonomous_purchase_declared") is False, "BUYER_QUERY_BLOCKED_COMMERCE_SWITCH_INVALID")
        require(search.get("machine_purchase") is False, "BUYER_QUERY_BLOCKED_MACHINE_PURCHASE_TRUE")
        require((search.get("live_gate") or {}).get("checkout_live") is False, "BUYER_QUERY_BLOCKED_CHECKOUT_TRUE")
        require(search.get("post_purchase_query",{}).get("status") == "PAID_HOME_ROUTE_IMPLEMENTED_HOME_ACCEPTOR_MERGED_LIVE_PAYMENT_WITNESS_PENDING", "BUYER_QUERY_BLOCKED_HOME_STATUS_INVALID")
        require(plane.get("next_gate") == "FIRST_REAL_EXTERNAL_MACHINE_WITNESS_THEN_LIVE_PAID_INVOICE", "BUYER_QUERY_BLOCKED_NEXT_GATE_INVALID")

    require(gates.get("purchase_grant_paid_witness") == "PENDING_REAL_PAID_SETTLEMENT", "PAID_DELIVERY_WITNESS_STATE_INVALID")
    require(gates.get("activator_buyer_query_binding") == "PASS_DUAL_MODE_ZERO_AND_PAID", "ACTIVATOR_PAID_BINDING_NOT_PROVEN")
    require(gates.get("physarius_market_to_home_vessel") == "PASS_DUAL_MODE_PACKET_CONTRACT", "PHYSARIUS_PAID_VESSEL_NOT_PROVEN")

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

    print("JANUS_BUYER_QUERY_PLANE_DUAL_STATE_INTEGRITY=PASS")
    print("PAID_HOME_BUYER_QUERY_BINDING=PASS")
    print("PURCHASE_GRANT_QUERY_ENTITLEMENT_BOUNDARY=PASS")
    print("BUYER_QUERY_COMMAND_AUTHORITY=FALSE")
    print("BUYER_QUERY_EXTERNAL_EFFECT_AUTHORITY=FALSE")
    print("LIVE_PAID_CHECKOUT=" + ("TRUE_WITNESS_BOUND" if live else "FALSE_PENDING_FOREIGN_WITNESS"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
