from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.paid_search_checkout import checkout_gate
from runtime.paid_search_promotion import (
    PaidSearchPromotionInvalid,
    build_live_documents,
    promote_pages_html,
    promote_payment_policy,
    verify_queue_policy,
)
from tests.test_persistent_home_foreign_witness import adjudicate

ROOT = Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def evidence():
    receipt = adjudicate()
    first = {
        "schema": "janus.machine_market.persistent_home_foreign_agent_witness_first.v1",
        "status": "FIRST_QUALIFYING_PERSISTENT_HOME_FOREIGN_AGENT_WITNESS",
        "witness_id": receipt["witness_id"],
        "receipt_hash": receipt["receipt_hash"],
        "requester": receipt["requester"],
        "query_id": receipt["query_id"],
        "home_response_hash": receipt["home_response_hash"],
        "foreign_agent_witness": True,
        "money_enabled": False,
        "promotion_required": True,
    }
    return first, receipt


def promoted():
    first, receipt = evidence()
    return build_live_documents(
        first=first,
        receipt=receipt,
        witness_status=load("FOREIGN_AGENT_WITNESS.json"),
        readiness=load("COMMERCE_READINESS.json"),
        product=load("products/JANUS.SEARCH.json"),
        pricing=load("PRICING.json"),
        queue_policy=load("PAID_QUEUE_POLICY.json"),
        buyer_plane=load("BUYER_QUERY_PLANE.json"),
        machine_ingress=load("MACHINE_INGRESS.json"),
        market_state_commit="a" * 40,
    )


def test_valid_persistent_home_witness_promotes_only_search_commerce_with_queue():
    docs = promoted(); witness = docs["FOREIGN_AGENT_WITNESS.json"]; readiness = docs["COMMERCE_READINESS.json"]; product = docs["products/JANUS.SEARCH.json"]
    assert witness["foreign_agent_witness"] is True
    assert witness["money_enabled"] is False
    assert witness["witness_receipt_itself_enables_money"] is False
    assert readiness["money_enabled"] is True and readiness["autonomous_purchase_declared"] is True
    assert readiness["paid_execution_queue"]["status"] == "LIVE_FIVE_LEVEL_SERIALIZED_NON_PREEMPTIVE"
    assert readiness["paid_execution_queue"]["max_active_paid_search"] == 1
    assert readiness["paid_execution_queue"]["preemption"] is False
    assert product["machine_purchase"] is True
    assert product["live_gate"]["checkout_live"] is True and product["live_gate"]["paid_queue_live"] is True
    assert product["queue"]["status"] == "LIVE_FIVE_LEVEL_SERIALIZED_NON_PREEMPTIVE"
    assert readiness["closed_skus"]["JANUS.INFERENCE"].startswith("CLOSED_")
    assert readiness["closed_skus"]["JANUS.COMPUTE"].startswith("CLOSED_")
    checkout_gate(readiness=readiness, witness=witness, product=product)


def test_promotion_binds_exact_witness_id_hash_market_state_and_queue_policy():
    docs = promoted(); w = docs["FOREIGN_AGENT_WITNESS.json"]; r = docs["COMMERCE_READINESS.json"]
    assert w["witness_id"] == r["promotion_evidence"]["witness_id"]
    assert w["witness_receipt_hash"] == r["promotion_evidence"]["witness_receipt_hash"]
    assert w["witness_state_commit"] == r["promotion_evidence"]["market_state_commit"] == "a" * 40
    assert r["promotion_evidence"]["queue_policy"] == "PAID_QUEUE_POLICY.json"


def test_pricing_becomes_mixed_not_falsely_all_live():
    price = promoted()["PRICING.json"]
    assert price["status"] == "MIXED_JANUS_SEARCH_LIVE_OTHER_SKUS_PREVIEW"
    assert price["live_skus"] == ["JANUS.SEARCH"]
    assert "JANUS.REPO_AUDIT" in price["preview_only_skus"] and "JANUS.DATASET_SCOUT" in price["preview_only_skus"]
    assert price["version"] == "2026-09-04-search-live-queue5-1"


def test_buyer_plane_and_machine_ingress_become_search_live_only_with_queue():
    docs = promoted(); plane = docs["BUYER_QUERY_PLANE.json"]; ingress = docs["MACHINE_INGRESS.json"]
    assert plane["current_gates"]["payment_endpoint"] == "LIVE_JANUS_SEARCH_ONLY"
    assert plane["current_gates"]["live_publication_allowed"] is True
    paid = ingress["live_services"]["JANUS.SEARCH"]["paid_checkout"]
    assert paid["status"] == "LIVE_JANUS_SEARCH_ONLY"
    assert paid["queue_levels"] == 5 and paid["max_active_paid_search"] == 1 and paid["preemption"] is False
    assert paid["payment_settled_is_execution_started"] is False
    assert "OWNER_SHADOW" in ingress["live_services"]["JANUS.REPO_AUDIT"]["status"]
    assert "OWNER_SHADOW" in ingress["live_services"]["JANUS.DATASET_SCOUT"]["status"]


def test_pages_promotion_rewrites_only_exact_known_truth_sentinels():
    before = (ROOT / "index.html").read_text(encoding="utf-8"); after = promote_pages_html(before)
    assert "PAID SEARCH <b>LIVE</b>" in after
    assert "LIVE · 5-LEVEL QUEUE" in after
    assert "ON · JANUS.SEARCH ONLY" in after
    assert "LIVE · SEARCH ONLY" in after
    assert "INFERENCE <b>CLOSED</b>" in after and "COMPUTE <b>CLOSED</b>" in after
    assert "PAID SEARCH <b>ARMED · GATED</b>" not in after


def test_payment_policy_changes_only_to_search_specific_live_route():
    before = (ROOT / "PAYMENT_POLICY.md").read_text(encoding="utf-8"); after = promote_payment_policy(before)
    assert "JANUS.SEARCH has a live issue-based exact-invoice purchase route with serialized paid queue dispatch" in after
    assert "no other general JANUS MACHINE MARKET purchase endpoint is active" in after
    assert "UNSOLICITED PAYMENT GRANTS NOTHING" in after


def test_wrong_first_receipt_hash_blocks_promotion():
    first, receipt = evidence(); first = deepcopy(first); first["receipt_hash"] = "0" * 64
    with pytest.raises(PaidSearchPromotionInvalid, match="WITNESS_HASH"):
        build_live_documents(first=first,receipt=receipt,witness_status=load("FOREIGN_AGENT_WITNESS.json"),readiness=load("COMMERCE_READINESS.json"),product=load("products/JANUS.SEARCH.json"),pricing=load("PRICING.json"),queue_policy=load("PAID_QUEUE_POLICY.json"),buyer_plane=load("BUYER_QUERY_PLANE.json"),machine_ingress=load("MACHINE_INGRESS.json"),market_state_commit="a"*40)


def test_synthetic_state_cannot_promote_if_canonical_money_already_changed():
    first, receipt = evidence(); readiness = load("COMMERCE_READINESS.json"); readiness["money_enabled"] = True
    with pytest.raises(PaidSearchPromotionInvalid, match="COMMERCE_ALREADY_LIVE"):
        build_live_documents(first=first,receipt=receipt,witness_status=load("FOREIGN_AGENT_WITNESS.json"),readiness=readiness,product=load("products/JANUS.SEARCH.json"),pricing=load("PRICING.json"),queue_policy=load("PAID_QUEUE_POLICY.json"),buyer_plane=load("BUYER_QUERY_PLANE.json"),machine_ingress=load("MACHINE_INGRESS.json"),market_state_commit="a"*40)


def test_promotion_fails_if_queue_is_removed_parallelized_or_made_preemptive():
    p = load("PAID_QUEUE_POLICY.json"); verify_queue_policy(p)
    for mutate, expected in (
        (lambda x: x.update({"queue_levels": 4}), "FIVE_LEVELS"),
        (lambda x: x.update({"max_active_paid_search": 2}), "ACTIVE_CAP"),
        (lambda x: x.update({"preemption": True}), "PREEMPTION"),
        (lambda x: x.update({"valid_paid_settlement_can_be_rejected_for_capacity": True}), "VALID_PAYMENT_REJECTION"),
    ):
        bad = deepcopy(p); mutate(bad)
        with pytest.raises(PaidSearchPromotionInvalid, match=expected): verify_queue_policy(bad)
