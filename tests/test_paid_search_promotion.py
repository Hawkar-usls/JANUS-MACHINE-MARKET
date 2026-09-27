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


def canonical_witness_live() -> bool:
    return load("FOREIGN_AGENT_WITNESS.json").get("foreign_agent_witness") is True


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
    if canonical_witness_live():
        pytest.skip("canonical witness already promoted")
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


def test_canonical_seller_is_live_independently_of_witness():
    readiness = load("COMMERCE_READINESS.json")
    product = load("products/JANUS.SEARCH.json")
    witness = load("FOREIGN_AGENT_WITNESS.json")
    assert readiness["seller_commerce_authorized"] is True
    assert readiness["money_enabled"] is True
    assert readiness["autonomous_purchase_declared"] is True
    assert product["machine_purchase"] is True
    assert product["live_gate"]["checkout_live"] is True
    assert product["live_gate"]["foreign_agent_witness_is_seller_prerequisite"] is False
    checkout_gate(readiness=readiness, witness=witness, product=product)


def test_valid_persistent_home_witness_promotes_evidence_not_seller_authority():
    docs = promoted()
    before_r = load("COMMERCE_READINESS.json")
    before_p = load("products/JANUS.SEARCH.json")
    w = docs["FOREIGN_AGENT_WITNESS.json"]
    r = docs["COMMERCE_READINESS.json"]
    p = docs["products/JANUS.SEARCH.json"]
    assert w["foreign_agent_witness"] is True
    assert w["money_enabled"] is False
    assert w["witness_receipt_itself_enables_money"] is False
    assert w["seller_commerce_was_already_live_before_witness"] is True
    assert r["seller_commerce_authorized"] is before_r["seller_commerce_authorized"] is True
    assert r["money_enabled"] is before_r["money_enabled"] is True
    assert r["autonomous_purchase_declared"] is before_r["autonomous_purchase_declared"] is True
    assert r["promotion_evidence"]["seller_authority_changed"] is False
    assert p["machine_purchase"] is before_p["machine_purchase"] is True
    assert p["live_gate"]["checkout_live"] is True
    assert p["live_gate"]["foreign_agent_witness"] is True
    assert p["live_gate"]["foreign_agent_witness_is_seller_prerequisite"] is False
    assert r["closed_skus"]["JANUS.INFERENCE"].startswith("CLOSED_")
    assert r["closed_skus"]["JANUS.COMPUTE"].startswith("CLOSED_")


def test_promotion_binds_exact_witness_id_hash_and_market_state():
    docs = promoted(); w = docs["FOREIGN_AGENT_WITNESS.json"]; r = docs["COMMERCE_READINESS.json"]
    assert w["witness_id"] == r["promotion_evidence"]["witness_id"]
    assert w["witness_receipt_hash"] == r["promotion_evidence"]["witness_receipt_hash"]
    assert w["witness_state_commit"] == r["promotion_evidence"]["market_state_commit"] == "a" * 40
    assert r["promotion_evidence"]["queue_policy"] == "PAID_QUEUE_POLICY.json"


def test_pricing_is_identical_before_and_after_witness_promotion():
    docs = promoted()
    assert docs["PRICING.json"] == load("PRICING.json")
    assert docs["PRICING.json"]["status"] == "MIXED_JANUS_SEARCH_LIVE_OTHER_SKUS_PREVIEW"
    assert docs["PRICING.json"]["live_skus"] == ["JANUS.SEARCH"]
    assert docs["PRICING.json"]["alternative_payment_routes"]["BTT_TRON"]["live_quote_allowed"] is False


def test_buyer_plane_and_machine_ingress_gain_witness_evidence_only():
    docs = promoted(); plane = docs["BUYER_QUERY_PLANE.json"]; ingress = docs["MACHINE_INGRESS.json"]
    assert plane["current_gates"]["payment_endpoint"] == "LIVE_JANUS_SEARCH_ONLY"
    assert plane["current_gates"]["live_publication_allowed"] is True
    assert plane["current_gates"]["foreign_buyer_query_witness"] == "PASS_PERSISTENT_HOME_EXTERNAL_MACHINE"
    paid = ingress["live_services"]["JANUS.SEARCH"]["paid_checkout"]
    assert paid["status"] == "LIVE_JANUS_SEARCH_ONLY"
    assert paid["foreign_agent_witness_is_seller_prerequisite"] is False
    assert ingress["proof"]["public_search_beta"]["external_roundtrip_observed"] is True
    assert ingress["proof"]["public_search_beta"]["foreign_agent_witness"] is True


def test_witness_promotion_does_not_rewrite_pages_or_payment_policy():
    before_html = (ROOT / "index.html").read_text(encoding="utf-8")
    before_policy = (ROOT / "PAYMENT_POLICY.md").read_text(encoding="utf-8")
    assert promote_pages_html(before_html) == before_html
    assert promote_payment_policy(before_policy) == before_policy
    assert "SELLER_COMMERCE_AUTHORIZED != FOREIGN_AGENT_WITNESS" in before_policy


def test_wrong_first_receipt_hash_blocks_promotion():
    if canonical_witness_live(): pytest.skip("canonical witness already promoted")
    first, receipt = evidence(); first = deepcopy(first); first["receipt_hash"] = "0" * 64
    with pytest.raises(PaidSearchPromotionInvalid, match="WITNESS_HASH"):
        build_live_documents(first=first,receipt=receipt,witness_status=load("FOREIGN_AGENT_WITNESS.json"),readiness=load("COMMERCE_READINESS.json"),product=load("products/JANUS.SEARCH.json"),pricing=load("PRICING.json"),queue_policy=load("PAID_QUEUE_POLICY.json"),buyer_plane=load("BUYER_QUERY_PLANE.json"),machine_ingress=load("MACHINE_INGRESS.json"),market_state_commit="a"*40)


def test_witness_promotion_refuses_to_be_source_of_seller_activation():
    if canonical_witness_live(): pytest.skip("canonical witness already promoted")
    first, receipt = evidence(); readiness = deepcopy(load("COMMERCE_READINESS.json")); readiness["seller_commerce_authorized"] = False
    with pytest.raises(PaidSearchPromotionInvalid, match="SELLER_COMMERCE_MUST_ALREADY_BE_AUTHORIZED"):
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
