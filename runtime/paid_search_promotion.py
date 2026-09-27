#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from runtime.persistent_home_foreign_witness import FIRST_SCHEMA, verify_witness_receipt


class PaidSearchPromotionInvalid(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PaidSearchPromotionInvalid(code)


def _closed_products(readiness: Mapping[str, Any]) -> None:
    closed = readiness.get("closed_skus") or {}
    require(str(closed.get("JANUS.INFERENCE") or "").startswith("CLOSED_"), "PROMOTION_INFERENCE_MUST_REMAIN_CLOSED")
    require(str(closed.get("JANUS.COMPUTE") or "").startswith("CLOSED_"), "PROMOTION_COMPUTE_MUST_REMAIN_CLOSED")


def verify_first_witness(first: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
    require(first.get("schema") == FIRST_SCHEMA, "PROMOTION_FIRST_WITNESS_SCHEMA_INVALID")
    require(first.get("status") == "FIRST_QUALIFYING_PERSISTENT_HOME_FOREIGN_AGENT_WITNESS", "PROMOTION_FIRST_WITNESS_STATUS_INVALID")
    require(first.get("foreign_agent_witness") is True, "PROMOTION_FIRST_WITNESS_FLAG_MISSING")
    require(first.get("money_enabled") is False, "PROMOTION_WITNESS_MUST_NOT_CARRY_SELLER_MONEY_AUTHORITY")
    require(first.get("promotion_required") is True, "PROMOTION_FIRST_WITNESS_MUST_REQUIRE_SEPARATE_PROMOTION")
    require(verify_witness_receipt(dict(receipt)), "PROMOTION_WITNESS_RECEIPT_INVALID")
    require(first.get("witness_id") == receipt.get("witness_id"), "PROMOTION_WITNESS_ID_MISMATCH")
    require(first.get("receipt_hash") == receipt.get("receipt_hash"), "PROMOTION_WITNESS_HASH_MISMATCH")
    require(receipt.get("foreign_agent_witness") is True, "PROMOTION_RECEIPT_FOREIGN_WITNESS_FALSE")
    require(receipt.get("promotion_authority") == "PERSISTENT_RECEIPT_CANDIDATE_ONLY", "PROMOTION_RECEIPT_AUTHORITY_INVALID")
    require(receipt.get("money_enabled") is False and receipt.get("paid_purchase") is False, "PROMOTION_RECEIPT_MUST_BE_ZERO_PRICE_EVIDENCE")


def verify_queue_policy(queue_policy: Mapping[str, Any]) -> None:
    require(queue_policy.get("schema") == "janus.machine_market.paid_search_queue_policy.v1", "PROMOTION_QUEUE_SCHEMA_INVALID")
    require(queue_policy.get("status") == "PREPARED_FOR_SEARCH_LIVE_PROMOTION", "PROMOTION_QUEUE_NOT_PREPARED")
    require(int(queue_policy.get("queue_levels", 0)) == 5, "PROMOTION_QUEUE_REQUIRES_FIVE_LEVELS")
    require(int(queue_policy.get("max_active_paid_search", 0)) == 1, "PROMOTION_QUEUE_ACTIVE_CAP_MUST_BE_ONE")
    require(queue_policy.get("preemption") is False, "PROMOTION_QUEUE_PREEMPTION_MUST_BE_FALSE")
    require(queue_policy.get("current_execution_can_be_interrupted_by_higher_tier") is False, "PROMOTION_QUEUE_ACTIVE_MUST_NOT_BE_INTERRUPTED")
    require(queue_policy.get("capacity_limit_applies_at") == "INVOICE_ADMISSION", "PROMOTION_QUEUE_CAPACITY_GATE_INVALID")
    require(queue_policy.get("valid_paid_settlement_can_be_rejected_for_capacity") is False, "PROMOTION_QUEUE_VALID_PAYMENT_REJECTION_FORBIDDEN")
    expected = {"1":10000,"2":15000,"3":22500,"4":35000,"5":50000}
    levels = queue_policy.get("levels") or {}
    for level, multiplier in expected.items():
        require(int((levels.get(level) or {}).get("price_multiplier_bps", 0)) == multiplier, "PROMOTION_QUEUE_LEVEL_PRICE_INVALID")


def _require_live_seller(readiness: Mapping[str, Any], product: Mapping[str, Any], pricing: Mapping[str, Any]) -> None:
    require(readiness.get("seller_commerce_authorized") is True, "PROMOTION_SELLER_COMMERCE_MUST_ALREADY_BE_AUTHORIZED")
    require(readiness.get("money_enabled") is True and readiness.get("autonomous_purchase_declared") is True, "PROMOTION_SELLER_COMMERCE_MUST_ALREADY_BE_LIVE")
    require(readiness.get("status") == "PAID_SEARCH_LIVE_FIRST_PAID_DELIVERY_PENDING", "PROMOTION_SELLER_STATUS_INVALID")
    require(product.get("sku") == "JANUS.SEARCH" and product.get("machine_purchase") is True, "PROMOTION_SEARCH_PRODUCT_MUST_ALREADY_BE_LIVE")
    gate = product.get("live_gate") or {}
    require(gate.get("checkout_live") is True and gate.get("paid_queue_live") is True, "PROMOTION_SEARCH_CHECKOUT_MUST_ALREADY_BE_LIVE")
    require(gate.get("foreign_agent_witness_is_seller_prerequisite") is False, "PROMOTION_WITNESS_MUST_NOT_BECOME_SELLER_GATE")
    require(pricing.get("status") == "MIXED_JANUS_SEARCH_LIVE_OTHER_SKUS_PREVIEW", "PROMOTION_PRICING_MUST_ALREADY_BE_SEARCH_LIVE")
    require(pricing.get("live_skus") == ["JANUS.SEARCH"], "PROMOTION_ONLY_SEARCH_MAY_BE_LIVE")
    _closed_products(readiness)


def build_live_documents(
    *, first: Mapping[str, Any], receipt: Mapping[str, Any], witness_status: Mapping[str, Any],
    readiness: Mapping[str, Any], product: Mapping[str, Any], pricing: Mapping[str, Any],
    queue_policy: Mapping[str, Any], buyer_plane: Mapping[str, Any], machine_ingress: Mapping[str, Any],
    market_state_commit: str,
) -> dict[str, dict[str, Any]]:
    """Promote only independent witness evidence; seller commerce is already live."""
    verify_first_witness(first, receipt)
    verify_queue_policy(queue_policy)
    _require_live_seller(readiness, product, pricing)
    require(len(str(market_state_commit)) == 40, "PROMOTION_MARKET_STATE_COMMIT_REQUIRED")
    require(witness_status.get("foreign_agent_witness") is False, "PROMOTION_CANONICAL_WITNESS_ALREADY_TRUE")

    wid = str(receipt["witness_id"]); rh = str(receipt["receipt_hash"])
    w = copy.deepcopy(dict(witness_status))
    w.update({
        "status": "PERSISTENT_HOME_EXTERNAL_MACHINE_WITNESS_CONFIRMED",
        "foreign_agent_witness": True,
        "promotion_authority": "PERSISTENT_HOME_RECEIPT_VERIFIED",
        "gate": "PASS_FIRST_REAL_EXTERNAL_MACHINE_PUBLIC_SEARCH_PERSISTENT_HOME_RECEIPT",
        "witness_id": wid,
        "witness_receipt_hash": rh,
        "witness_state_commit": str(market_state_commit),
        "witness_state_path": f"state/r1-foreign-home/receipts/{wid}.json",
        "money_enabled": False,
        "autonomous_purchase_declared": False,
        "persistent_home_result_required_for_paid_promotion": False,
        "witness_receipt_itself_enables_money": False,
        "seller_commerce_was_already_live_before_witness": True,
    })

    r = copy.deepcopy(dict(readiness))
    r["promotion_evidence"] = {
        "kind": "FOREIGN_AGENT_WITNESS_EVIDENCE_ONLY",
        "witness_id": wid,
        "witness_receipt_hash": rh,
        "market_state_commit": str(market_state_commit),
        "source": "state/r1-foreign-home/FIRST.json",
        "queue_policy": "PAID_QUEUE_POLICY.json",
        "seller_authority_changed": False,
    }
    r["required_live_gates"]["foreign_agent_witness"] = True
    r["required_live_gates"]["foreign_agent_witness_is_seller_prerequisite"] = False
    _closed_products(r)

    p = copy.deepcopy(dict(product))
    p["live_gate"]["foreign_agent_witness"] = True
    p["live_gate"]["witness_id"] = wid
    p["live_gate"]["witness_receipt_hash"] = rh
    p["live_gate"]["foreign_agent_witness_is_seller_prerequisite"] = False

    price = copy.deepcopy(dict(pricing))

    plane = copy.deepcopy(dict(buyer_plane))
    plane["current_gates"]["foreign_buyer_query_witness"] = "PASS_PERSISTENT_HOME_EXTERNAL_MACHINE"
    plane["current_gates"]["foreign_witness_id"] = wid
    plane["current_gates"]["foreign_agent_witness_is_seller_prerequisite"] = False

    ingress = copy.deepcopy(dict(machine_ingress))
    ingress["current_commerce_state"]["foreign_agent_witness"] = True
    ingress["current_commerce_state"]["foreign_agent_witness_is_seller_prerequisite"] = False
    proof = ingress.setdefault("proof", {}).setdefault("public_search_beta", {})
    proof["external_roundtrip_observed"] = True
    proof["foreign_agent_witness"] = True
    proof["witness_id"] = wid

    return {
        "FOREIGN_AGENT_WITNESS.json": w,
        "COMMERCE_READINESS.json": r,
        "products/JANUS.SEARCH.json": p,
        "PRICING.json": price,
        "BUYER_QUERY_PLANE.json": plane,
        "MACHINE_INGRESS.json": ingress,
    }


def promote_pages_html(text: str) -> str:
    return text


def promote_payment_policy(text: str) -> str:
    return text


def write_live_promotion(*, root: str | Path, state_root: str | Path, market_state_commit: str) -> dict[str, Any]:
    root = Path(root); state_root = Path(state_root)
    first_path = state_root / "state/r1-foreign-home/FIRST.json"
    require(first_path.is_file(), "PROMOTION_FIRST_WITNESS_MISSING")
    first = json.loads(first_path.read_text(encoding="utf-8"))
    receipt_path = state_root / "state/r1-foreign-home/receipts" / f"{first['witness_id']}.json"
    require(receipt_path.is_file(), "PROMOTION_WITNESS_RECEIPT_MISSING")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    def load(rel: str) -> dict[str, Any]:
        return json.loads((root / rel).read_text(encoding="utf-8"))

    docs = build_live_documents(
        first=first, receipt=receipt,
        witness_status=load("FOREIGN_AGENT_WITNESS.json"),
        readiness=load("COMMERCE_READINESS.json"),
        product=load("products/JANUS.SEARCH.json"),
        pricing=load("PRICING.json"),
        queue_policy=load("PAID_QUEUE_POLICY.json"),
        buyer_plane=load("BUYER_QUERY_PLANE.json"),
        machine_ingress=load("MACHINE_INGRESS.json"),
        market_state_commit=market_state_commit,
    )
    for rel, data in docs.items():
        if rel == "PRICING.json":
            continue
        (root / rel).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "FOREIGN_AGENT_WITNESS_EVIDENCE_PROMOTION_CANDIDATE",
        "witness_id": receipt["witness_id"],
        "receipt_hash": receipt["receipt_hash"],
        "market_state_commit": market_state_commit,
        "seller_authority_changed": False,
        "money_enabled_by_witness": False,
    }


__all__ = ["PaidSearchPromotionInvalid","build_live_documents","promote_pages_html","promote_payment_policy","verify_first_witness","verify_queue_policy","write_live_promotion"]
