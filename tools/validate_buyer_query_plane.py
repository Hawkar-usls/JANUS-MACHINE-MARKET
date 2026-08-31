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
        plane.get("status") == "ZERO_PRICE_HOME_ROUNDTRIP_PROVEN__PAID_LANE_ARMED_DISABLED",
        "BUYER_QUERY_PLANE_STATUS_DRIFT",
    )
    zero = plane.get("proven_zero_price_witness") or {}
    require(zero.get("status") == "GREEN", "R1B_ZERO_PRICE_WITNESS_MISSING")
    require(zero.get("money_enabled") is False, "R1B_ZERO_PRICE_MONEY_MUST_BE_FALSE")
    require(zero.get("foreign_buyer_witness") is False, "R1B_OWNER_SHADOW_MUST_NOT_BECOME_FOREIGN_WITNESS")
    require(zero.get("exact_retry_second_cognition") is False, "R1B_EXACT_RETRY_SECOND_COGNITION_FORBIDDEN")

    gates = plane.get("current_gates") or {}
    require(gates.get("payment_endpoint") == "CLOSED_PRICE_NOT_PUBLISHED", "PAYMENT_ENDPOINT_MUST_REMAIN_CLOSED")
    require(gates.get("purchase_grant_paid_witness") == "PENDING", "PAID_WITNESS_MUST_REMAIN_PENDING")
    require(gates.get("activator_buyer_query_binding") == "PROVEN_ZERO_PRICE", "ACTIVATOR_ZERO_PRICE_BINDING_NOT_RECORDED")
    require(gates.get("physarius_market_to_home_vessel") == "PROVEN_ZERO_PRICE_CREDENTIALLESS_ROUNDTRIP", "PHYSARIUS_ZERO_PRICE_ROUNDTRIP_NOT_RECORDED")
    require(gates.get("exact_retry_no_second_cognition") == "PROVEN_ZERO_PRICE", "R1B_REPLAY_WITNESS_NOT_RECORDED")
    require(gates.get("foreign_buyer_query_witness") == "PENDING", "FOREIGN_BUYER_WITNESS_MUST_REMAIN_PENDING")
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
        post.get("status") == "ZERO_PRICE_HOME_ROUNDTRIP_PROVEN__PAID_BINDING_PREPARED",
        "JANUS_SEARCH_POST_PURCHASE_QUERY_STATUS_DRIFT",
    )
    paid_runtime = search.get("paid_runtime") or {}
    require(paid_runtime.get("status") == "ARMED_DISABLED", "JANUS_SEARCH_PAID_RUNTIME_MUST_REMAIN_DISABLED")
    require(paid_runtime.get("real_paid_roundtrip_witness") is False, "JANUS_SEARCH_PAID_WITNESS_PREMATURE")
    require(post.get("enabled_only_by_explicit_purchase_grant_entitlement") is True, "QUERY_ENTITLEMENT_GATE_MISSING")
    require(post.get("query_is_command") is False, "QUERY_MUST_NOT_BECOME_COMMAND")
    require(post.get("external_effect_authorized") is False, "QUERY_EXTERNAL_EFFECTS_FORBIDDEN")

    require(plane.get("next_gate") == "R2_REAL_PAID_JANUS_SEARCH_ROUNDTRIP", "R2_NEXT_GATE_MISMATCH")

    print("JANUS_BUYER_QUERY_PLANE_ZERO_PRICE_PROVEN=PASS")
    print("PURCHASE_GRANT_QUERY_ENTITLEMENT_BOUNDARY=PASS")
    print("BUYER_QUERY_COMMAND_AUTHORITY=FALSE")
    print("BUYER_QUERY_EXTERNAL_EFFECT_AUTHORITY=FALSE")
    print("R2_LIVE_PAYMENT_QUERY=FALSE_PRICE_NOT_PUBLISHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
