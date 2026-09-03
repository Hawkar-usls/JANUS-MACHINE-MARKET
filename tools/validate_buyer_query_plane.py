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

    require(
        plane.get("status") == "ZERO_PRICE_LIVE_PAID_HOME_ROUTE_ARMED_WITNESS_PENDING",
        "BUYER_QUERY_PLANE_STATUS_STALE_OR_UNSAFE",
    )
    gates = plane.get("current_gates") or {}
    require(gates.get("payment_endpoint") == "ARMED_GATE_CLOSED", "PAYMENT_ENDPOINT_MUST_REMAIN_GATE_CLOSED")
    require(gates.get("purchase_grant_paid_witness") == "PENDING_REAL_PAID_SETTLEMENT", "PAID_WITNESS_MUST_REMAIN_PENDING")
    require(gates.get("activator_buyer_query_binding") == "PASS_DUAL_MODE_ZERO_AND_PAID", "ACTIVATOR_PAID_BINDING_NOT_PROVEN")
    require(gates.get("physarius_market_to_home_vessel") == "PASS_DUAL_MODE_PACKET_CONTRACT", "PHYSARIUS_PAID_VESSEL_NOT_PROVEN")
    require(gates.get("foreign_buyer_query_witness") == "PENDING", "FOREIGN_BUYER_WITNESS_PREMATURE")
    require(gates.get("live_publication_allowed") is False, "LIVE_BUYER_QUERY_PUBLICATION_FORBIDDEN")

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
    require(search.get("machine_purchase") is False, "JANUS_SEARCH_MACHINE_PURCHASE_PREMATURE")
    require(
        post.get("status") == "PAID_HOME_ROUTE_IMPLEMENTED_HOME_ACCEPTOR_MERGED_LIVE_PAYMENT_WITNESS_PENDING",
        "JANUS_SEARCH_PAID_HOME_STATUS_STALE_OR_UNSAFE",
    )
    require(post.get("enabled_only_by_explicit_purchase_grant_entitlement") is True, "QUERY_ENTITLEMENT_GATE_MISSING")
    require(post.get("query_is_command") is False, "QUERY_MUST_NOT_BECOME_COMMAND")
    require(post.get("payment_is_command") is False, "PAYMENT_MUST_NOT_BECOME_COMMAND")
    require(post.get("purchase_grant_is_execution_authority") is False, "PURCHASE_GRANT_MUST_NOT_BECOME_EXECUTION_AUTHORITY")
    require(post.get("external_effect_authorized") is False, "QUERY_EXTERNAL_EFFECTS_FORBIDDEN")
    require((search.get("live_gate") or {}).get("checkout_live") is False, "CHECKOUT_LIVE_PREMATURE")

    require(
        plane.get("next_gate") == "FIRST_REAL_EXTERNAL_MACHINE_WITNESS_THEN_LIVE_PAID_INVOICE",
        "BUYER_QUERY_NEXT_GATE_MISMATCH",
    )

    print("JANUS_BUYER_QUERY_PLANE_FAIL_CLOSED=PASS")
    print("PAID_HOME_BUYER_QUERY_BINDING=PASS")
    print("PURCHASE_GRANT_QUERY_ENTITLEMENT_BOUNDARY=PASS")
    print("BUYER_QUERY_COMMAND_AUTHORITY=FALSE")
    print("BUYER_QUERY_EXTERNAL_EFFECT_AUTHORITY=FALSE")
    print("LIVE_PAID_CHECKOUT=FALSE_PENDING_FOREIGN_WITNESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
