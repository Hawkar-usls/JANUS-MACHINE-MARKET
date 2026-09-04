#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from runtime.persistent_home_foreign_witness import (
    FIRST_SCHEMA,
    verify_witness_receipt,
)


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
    require(first.get("money_enabled") is False, "PROMOTION_WITNESS_MUST_PRECEDE_MONEY")
    require(first.get("promotion_required") is True, "PROMOTION_FIRST_WITNESS_MUST_REQUIRE_SEPARATE_PROMOTION")
    require(verify_witness_receipt(receipt), "PROMOTION_WITNESS_RECEIPT_INVALID")
    require(first.get("witness_id") == receipt.get("witness_id"), "PROMOTION_WITNESS_ID_MISMATCH")
    require(first.get("receipt_hash") == receipt.get("receipt_hash"), "PROMOTION_WITNESS_HASH_MISMATCH")
    require(receipt.get("foreign_agent_witness") is True, "PROMOTION_RECEIPT_FOREIGN_WITNESS_FALSE")
    require(receipt.get("promotion_authority") == "PERSISTENT_RECEIPT_CANDIDATE_ONLY", "PROMOTION_RECEIPT_AUTHORITY_INVALID")
    require(receipt.get("money_enabled") is False and receipt.get("paid_purchase") is False, "PROMOTION_RECEIPT_MUST_BE_ZERO_PRICE_EVIDENCE")


def build_live_documents(
    *,
    first: Mapping[str, Any],
    receipt: Mapping[str, Any],
    witness_status: Mapping[str, Any],
    readiness: Mapping[str, Any],
    product: Mapping[str, Any],
    pricing: Mapping[str, Any],
    buyer_plane: Mapping[str, Any],
    machine_ingress: Mapping[str, Any],
    market_state_commit: str,
) -> dict[str, dict[str, Any]]:
    verify_first_witness(first, receipt)
    require(len(str(market_state_commit)) == 40, "PROMOTION_MARKET_STATE_COMMIT_REQUIRED")
    require(witness_status.get("foreign_agent_witness") is False, "PROMOTION_CANONICAL_WITNESS_ALREADY_TRUE")
    require(readiness.get("money_enabled") is False and readiness.get("autonomous_purchase_declared") is False, "PROMOTION_COMMERCE_ALREADY_LIVE_OR_INCONSISTENT")
    require(product.get("sku") == "JANUS.SEARCH" and product.get("machine_purchase") is False, "PROMOTION_SEARCH_PRODUCT_NOT_CLOSED")
    require((product.get("live_gate") or {}).get("checkout_live") is False, "PROMOTION_CHECKOUT_ALREADY_LIVE")
    _closed_products(readiness)

    wid = str(receipt["witness_id"])
    rh = str(receipt["receipt_hash"])

    w = copy.deepcopy(dict(witness_status))
    w.update({
        "status": "PERSISTENT_HOME_EXTERNAL_MACHINE_WITNESS_CONFIRMED",
        "foreign_agent_witness": True,
        "promotion_authority": "PERSISTENT_HOME_RECEIPT_VERIFIED",
        "gate": "PASS_FIRST_REAL_EXTERNAL_MACHINE_PUBLIC_SEARCH_PERSISTENT_HOME_RECEIPT",
        "witness_id": wid,
        "witness_receipt_hash": rh,
        "witness_state_commit": market_state_commit,
        "witness_state_path": f"state/r1-foreign-home/receipts/{wid}.json",
        "money_enabled": False,
        "autonomous_purchase_declared": False,
        "persistent_home_result_required_for_paid_promotion": True,
        "witness_receipt_itself_enables_money": False,
        "paid_commerce_promotion_eligible": True,
    })

    r = copy.deepcopy(dict(readiness))
    r["status"] = "PAID_SEARCH_LIVE_FIRST_PAID_DELIVERY_PENDING"
    r["money_enabled"] = True
    r["autonomous_purchase_declared"] = True
    r["reason"] = "A qualifying external machine-client completed the frozen public SEARCH -> credentialless persistent JANUS HOME/HRAiN -> Market receipt gate. JANUS.SEARCH live issue invoices may now be issued; payment still grants no command or external-effect authority."
    r["payment_rail"]["state"] = "LIVE_INVOICE_TX_PROOF_JANUS_SEARCH_ONLY"
    gates = r["required_live_gates"]
    gates["foreign_agent_witness"] = True
    gates["money_enabled_policy"] = True
    gates["product_machine_purchase"] = True
    gates["transaction_endpoint"] = "GITHUB_ISSUE_INVOICE_AND_TX_PROOF_ENDPOINT_LIVE_JANUS_SEARCH_ONLY"
    gates["fresh_checkout_replay"] = "REQUIRED_ON_FIRST_REAL_PAID_WITNESS"
    gates["first_real_paid_delivery"] = "PENDING"
    r["promotion_evidence"] = {
        "witness_id": wid,
        "witness_receipt_hash": rh,
        "market_state_commit": market_state_commit,
        "source": "state/r1-foreign-home/FIRST.json",
    }
    r["next_gate"] = "FIRST_REAL_PAID_SEARCH_SETTLEMENT_PERSISTENT_HOME_RESULT_RECEIPT"
    _closed_products(r)

    p = copy.deepcopy(dict(product))
    p["status"] = "PAID_LIVE_FIRST_DELIVERY_PENDING"
    p["machine_purchase"] = True
    p["request"]["mode"] = "GITHUB_ISSUE_CHECKOUT_LIVE"
    p["pricing"]["mode"] = "RATECARD_PUBLISHED_LIVE_INVOICE"
    p["post_purchase_query"]["status"] = "PAID_HOME_ROUTE_LIVE_FIRST_PAID_DELIVERY_PENDING"
    p["live_gate"] = {
        "foreign_agent_witness": True,
        "money_enabled": True,
        "machine_purchase": True,
        "checkout_live": True,
        "witness_id": wid,
        "witness_receipt_hash": rh,
    }

    price = copy.deepcopy(dict(pricing))
    price["status"] = "MIXED_JANUS_SEARCH_LIVE_OTHER_SKUS_PREVIEW"
    price["version"] = "2026-09-04-search-live-1"
    price["live_skus"] = ["JANUS.SEARCH"]
    price["preview_only_skus"] = [
        "JANUS.DATASET_SCOUT",
        "JANUS.EVIDENCE_PACK",
        "JANUS.ARCHIVE_SCAN",
        "JANUS.REPO_AUDIT",
        "JANUS.RESEARCH_JOB",
    ]
    price["pricing_law"] = "JANUS.SEARCH browser totals remain non-authoritative previews until the trusted live issue checkout freezes an exact invoice. Other local rates remain preview-only. PAYMENT != EXECUTION_AUTHORITY."

    plane = copy.deepcopy(dict(buyer_plane))
    plane["status"] = "ZERO_PRICE_AND_PAID_SEARCH_LIVE_FIRST_PAID_DELIVERY_PENDING"
    plane["current_gates"]["payment_endpoint"] = "LIVE_JANUS_SEARCH_ONLY"
    plane["current_gates"]["purchase_grant_paid_witness"] = "PENDING_REAL_PAID_SETTLEMENT"
    plane["current_gates"]["foreign_buyer_query_witness"] = "PASS_PERSISTENT_HOME_EXTERNAL_MACHINE"
    plane["current_gates"]["live_publication_allowed"] = True
    plane["current_gates"]["foreign_witness_id"] = wid
    plane["next_gate"] = "FIRST_REAL_PAID_SEARCH_SETTLEMENT_PERSISTENT_HOME_RESULT_RECEIPT"

    ingress = copy.deepcopy(dict(machine_ingress))
    search = ingress["live_services"]["JANUS.SEARCH"]
    search["status"] = "LIVE_PUBLIC_ZERO_PRICE_BETA_PLUS_PAID_ISSUE_CHECKOUT"
    search["paid_checkout"] = {
        "status": "LIVE_JANUS_SEARCH_ONLY",
        "title_prefix": "[JANUS PAID SEARCH]",
        "workflow": ".github/workflows/paid-search-checkout.yml",
        "machine_purchase": True,
        "payment_required": True,
        "payment_is_command": False,
    }
    ingress["current_commerce_state"].update({
        "price_mode": "ZERO_PRICE_PUBLIC_BETA_PLUS_LIVE_PAID_SEARCH_OTHER_LANES_CLOSED_OR_SHADOW",
        "money_enabled": True,
        "autonomous_purchase_declared": True,
        "payment_required": "ONLY_FOR_PAID_JANUS_SEARCH_ISSUES",
    })
    ingress["proof"]["public_search_beta"]["external_roundtrip_observed"] = True
    ingress["proof"]["public_search_beta"]["foreign_agent_witness"] = True
    ingress["proof"]["public_search_beta"]["witness_id"] = wid

    return {
        "FOREIGN_AGENT_WITNESS.json": w,
        "COMMERCE_READINESS.json": r,
        "products/JANUS.SEARCH.json": p,
        "PRICING.json": price,
        "BUYER_QUERY_PLANE.json": plane,
        "MACHINE_INGRESS.json": ingress,
    }


def promote_pages_html(text: str) -> str:
    replacements = {
        '<span class="truth prep">PAID SEARCH <b>ARMED · GATED</b></span>': '<span class="truth live">PAID SEARCH <b>LIVE</b></span>',
        '<div><span>Paid checkout</span><b class="amber">ARMED · WITNESS GATE</b></div>': '<div><span>Paid checkout</span><b>LIVE · EXACT INVOICE</b></div>',
        '<div><span>Autonomous purchase</span><b>OFF UNTIL GATE</b></div>': '<div><span>Autonomous purchase</span><b>ON · JANUS.SEARCH ONLY</b></div>',
        'The paid SEARCH transport, invoice, exact Ethereum-USDT observer and persistent HOME delivery path are armed. No payable invoice is issued until the independent external-witness gate is satisfied. <b>Do not send funds without a live invoice for your exact request.</b>': 'Paid JANUS.SEARCH is live through the exact issue-invoice route. A payable invoice is created only for an admitted request. <b>Do not send funds without the live invoice for your exact request.</b>',
        '<p>Pending a genuine independent external GitHub principal completing the public Market → persistent HOME/JANUS → Market result roundtrip.</p><b class="status-big amber">PENDING</b>': '<p>A qualifying independent machine-client completed the frozen public Market → persistent HOME/JANUS → Market result roundtrip.</p><b class="status-big cyan">PASS</b>',
        '<p>The issue checkout endpoint, immutable invoice contract, exact Ethereum-mainnet USDT transaction observer, purchase ledger and persistent HOME delivery path are implemented and CI-proven. Live invoices remain witness-gated.</p><b class="status-big amber">ARMED · GATED</b>': '<p>JANUS.SEARCH issue checkout is live: exact invoices, Ethereum-mainnet USDT observation, purchase ledger and persistent HOME delivery remain fail-closed and receipt-bound.</p><b class="status-big cyan">LIVE · SEARCH ONLY</b>',
        '<div class="confirm-box pending"><span>JANUS ACCEPT</span><b>WITNESS GATE PENDING</b></div>': '<div class="confirm-box"><span>JANUS ACCEPT</span><b>LIVE SEARCH GATE</b></div>',
    }
    out = text
    for old, new in replacements.items():
        require(old in out, "PROMOTION_PAGES_SENTINEL_MISSING")
        out = out.replace(old, new, 1)
    return out


def promote_payment_policy(text: str) -> str:
    old = "The market publishes a declared USDT / Ethereum receiving route for machine-readable policy work, but **no general JANUS MACHINE MARKET purchase endpoint is currently active**."
    new = "The market publishes a declared USDT / Ethereum receiving route. **JANUS.SEARCH has a live issue-based exact-invoice purchase route; no other general JANUS MACHINE MARKET purchase endpoint is active.**"
    require(old in text, "PROMOTION_PAYMENT_POLICY_SENTINEL_MISSING")
    return text.replace(old, new, 1)


def write_live_promotion(
    *, root: str | Path, state_root: str | Path, market_state_commit: str
) -> dict[str, Any]:
    root = Path(root); state_root = Path(state_root)
    first = json.loads((state_root / "state/r1-foreign-home/FIRST.json").read_text(encoding="utf-8"))
    receipt = json.loads((state_root / "state/r1-foreign-home/receipts" / f"{first['witness_id']}.json").read_text(encoding="utf-8"))
    load = lambda rel: json.loads((root / rel).read_text(encoding="utf-8"))
    docs = build_live_documents(
        first=first,
        receipt=receipt,
        witness_status=load("FOREIGN_AGENT_WITNESS.json"),
        readiness=load("COMMERCE_READINESS.json"),
        product=load("products/JANUS.SEARCH.json"),
        pricing=load("PRICING.json"),
        buyer_plane=load("BUYER_QUERY_PLANE.json"),
        machine_ingress=load("MACHINE_INGRESS.json"),
        market_state_commit=market_state_commit,
    )
    for rel, value in docs.items():
        (root / rel).write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (root / "index.html").write_text(promote_pages_html((root / "index.html").read_text(encoding="utf-8")),encoding="utf-8")
    (root / "PAYMENT_POLICY.md").write_text(promote_payment_policy((root / "PAYMENT_POLICY.md").read_text(encoding="utf-8")),encoding="utf-8")
    return {"witness_id": first["witness_id"], "receipt_hash": first["receipt_hash"], "market_state_commit": market_state_commit, "changed": sorted([*docs.keys(),"index.html","PAYMENT_POLICY.md"])}
