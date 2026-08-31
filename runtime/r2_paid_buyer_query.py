#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PAID_REQUEST_SCHEMA = "janus.machine_market.paid_buyer_query_request.v1"
PAYMENT_RECEIPT_SCHEMA = "janus.machine_market.payment_receipt.v1"
GRANT_SCHEMA = "janus.machine_market.purchase_grant.v1"
QUERY_SCHEMA = "janus.machine_market.buyer_query.v1"
PACKET_SCHEMA = "janus.machine_market.home_paid_buyer_query_packet.v1"
MARKET_REPOSITORY = "Hawkar-usls/JANUS-MACHINE-MARKET"
HOME_REPOSITORY = "Hawkar-usls/Hawkar-usls"
SKU = "JANUS.SEARCH"


class PaidBuyerQueryError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PaidBuyerQueryError(code)


def normalize_request(request: dict[str, Any], price: dict[str, Any]) -> dict[str, Any]:
    require(request.get("schema") == PAID_REQUEST_SCHEMA, "R2_REQUEST_SCHEMA_INVALID")
    require(price.get("schema") == "janus.machine_market.price.v1", "R2_PRICE_SCHEMA_INVALID")
    require(price.get("sku") == SKU, "R2_PRICE_SKU_INVALID")
    require(price.get("status") == "PUBLISHED", "R2_PRICE_NOT_PUBLISHED")
    require(price.get("machine_purchase_enabled") is True, "R2_MACHINE_PURCHASE_NOT_ENABLED")
    amount_atomic = price.get("amount_atomic")
    require(isinstance(amount_atomic, int) and not isinstance(amount_atomic, bool) and amount_atomic > 0, "R2_PRICE_AMOUNT_INVALID")

    request_id = str(request.get("request_id") or "").strip()
    buyer_actor_id = str(request.get("buyer_actor_id") or "").strip()
    conversation_id = str(request.get("conversation_id") or "").strip()
    message_text = str(request.get("message_text") or "").strip()
    created_at = str(request.get("created_at") or "").strip()
    tx_hash = str(request.get("tx_hash") or "").lower().strip()
    turn_index = int(request.get("turn_index", 0))
    require(bool(request_id), "R2_REQUEST_ID_REQUIRED")
    require(bool(buyer_actor_id), "R2_BUYER_ACTOR_REQUIRED")
    require(bool(conversation_id), "R2_CONVERSATION_ID_REQUIRED")
    require(bool(message_text), "R2_MESSAGE_REQUIRED")
    require(bool(created_at), "R2_CREATED_AT_REQUIRED")
    require(tx_hash.startswith("0x") and len(tx_hash) == 66, "R2_TX_HASH_INVALID")
    max_turns = int(price.get("buyer_query_turns", 1))
    max_message = int(price.get("max_message_utf8_bytes", 8000))
    max_answer = int(price.get("max_answer_utf8_bytes", 12000))
    history_turns = int(price.get("conversation_history_turns", 8))
    require(1 <= max_turns <= 100, "R2_MAX_TURNS_INVALID")
    require(0 <= turn_index < max_turns, "R2_TURN_BUDGET_EXHAUSTED")
    require(len(message_text.encode("utf-8")) <= max_message <= 32000, "R2_MESSAGE_LIMIT_EXCEEDED")
    require(1 <= max_answer <= 64000, "R2_ANSWER_LIMIT_INVALID")
    require(0 <= history_turns <= 32, "R2_HISTORY_LIMIT_INVALID")
    return {
        "schema": PAID_REQUEST_SCHEMA,
        "request_id": request_id,
        "sku": SKU,
        "buyer_actor_id": buyer_actor_id,
        "conversation_id": conversation_id,
        "turn_index": turn_index,
        "message_text": message_text,
        "created_at": created_at,
        "tx_hash": tx_hash,
        "source_issue_number": request.get("source_issue_number"),
        "source_issue_id": request.get("source_issue_id"),
        "request_origin": str(request.get("request_origin") or "MACHINE_PURCHASE"),
        "max_turns": max_turns,
        "max_message_utf8_bytes": max_message,
        "max_answer_utf8_bytes": max_answer,
        "conversation_history_turns": history_turns,
        "amount_atomic": amount_atomic,
    }


def verify_payment_receipt(payment: dict[str, Any], *, route: dict[str, Any], norm: dict[str, Any]) -> bool:
    if not isinstance(payment, dict) or payment.get("schema") != PAYMENT_RECEIPT_SCHEMA:
        return False
    body = dict(payment)
    claimed = str(body.pop("receipt_hash", ""))
    if len(claimed) != 64 or digest(body) != claimed:
        return False
    if payment.get("verification_status") != "VERIFIED_EXACT_ERC20_TRANSFER":
        return False
    if payment.get("route_id") != route.get("route_id"):
        return False
    if payment.get("chain_id") != 1 or payment.get("asset") != "USDT":
        return False
    if str(payment.get("tx_hash") or "").lower() != norm["tx_hash"]:
        return False
    if payment.get("amount_atomic") != norm["amount_atomic"]:
        return False
    asset = route.get("asset") or {}
    merchant = route.get("merchant") or {}
    if str(payment.get("token_contract") or "").lower() != str(asset.get("contract") or "").lower():
        return False
    if str(payment.get("to_address") or "").lower() != str(merchant.get("receiving_address") or "").lower():
        return False
    if int(payment.get("confirmations") or 0) < int((route.get("verification") or {}).get("minimum_confirmations", 12)):
        return False
    return True


def build_paid_packet(
    request: dict[str, Any],
    *,
    price: dict[str, Any],
    route: dict[str, Any],
    payment_receipt: dict[str, Any],
) -> dict[str, Any]:
    require(route.get("schema") == "janus.machine_market.payment_route.v1", "R2_PAYMENT_ROUTE_SCHEMA_INVALID")
    require(route.get("live_payment_enabled") is True, "R2_LIVE_PAYMENT_ROUTE_NOT_ENABLED")
    norm = normalize_request(request, price)
    require(verify_payment_receipt(payment_receipt, route=route, norm=norm), "R2_PAYMENT_RECEIPT_INVALID")
    request_hash = digest(norm)
    offer = {
        "schema": "janus.machine_market.paid_offer.v1",
        "sku": SKU,
        "price": {
            "asset": "USDT",
            "network": "ethereum-mainnet",
            "amount_atomic": norm["amount_atomic"],
            "decimals": 6,
        },
        "price_manifest_hash": digest(price),
        "payment_route_id": route["route_id"],
        "buyer_query_turns": norm["max_turns"],
        "production_purchase": True,
    }
    offer_hash = digest(offer)
    payment_reference = str(payment_receipt["payment_reference"])
    payment_receipt_hash = str(payment_receipt["receipt_hash"])
    purchase_id = "pur-paid-" + digest({
        "request_id": norm["request_id"],
        "request_hash": request_hash,
        "offer_hash": offer_hash,
        "payment_reference": payment_reference,
    })[:40]
    entitlement_nonce = "paid-" + digest({
        "purchase_id": purchase_id,
        "payment_reference": payment_reference,
        "purpose": "R2_PAID_BUYER_QUERY_ENTITLEMENT",
    })[:40]
    grant = {
        "schema": GRANT_SCHEMA,
        "purchase_id": purchase_id,
        "sku": SKU,
        "offer_hash": offer_hash,
        "request_hash": request_hash,
        "terms_hash": digest({"payment_policy": "PAYMENT_POLICY.md", "price_manifest_hash": offer["price_manifest_hash"]}),
        "payment_reference": payment_reference,
        "status": "PURCHASE_ELIGIBLE",
        "execution_authority_granted": False,
        "allowed_operation": "REQUEST_BOUNDED_BUYER_QUERY",
        "authority_ceiling": {
            "conversation_mode": "READ_ONLY_HRAIN_MEMORY_BOUND",
            "external_effects": False,
            "repository_write": False,
            "shell": False,
            "secret_access": False,
            "scientific_claim_promotion": False,
            "production_effect_authority": False,
        },
        "buyer_query_entitlement": {
            "enabled": True,
            "buyer_actor_id": norm["buyer_actor_id"],
            "max_turns": norm["max_turns"],
            "max_message_utf8_bytes": norm["max_message_utf8_bytes"],
            "max_answer_utf8_bytes": norm["max_answer_utf8_bytes"],
            "conversation_history_turns": norm["conversation_history_turns"],
            "entitlement_nonce": entitlement_nonce,
            "read_only_conversation": True,
            "external_effect_authorized": False,
        },
        "expires_at": None,
        "reasons": [
            "R2_EXACT_USDT_PAYMENT_VERIFIED",
            "PURCHASE_GRANT_IS_NOT_EXECUTION_AUTHORITY",
            "BUYER_QUERY_IS_NOT_COMMAND_AUTHORITY",
        ],
    }
    purchase_grant_hash = digest(grant)
    message_hash = digest(norm["message_text"])
    query_id = "bq-" + digest({
        "purchase_id": purchase_id,
        "conversation_id": norm["conversation_id"],
        "turn_index": norm["turn_index"],
        "message_hash": message_hash,
        "entitlement_nonce": entitlement_nonce,
    })
    query = {
        "schema": QUERY_SCHEMA,
        "purchase_id": purchase_id,
        "purchase_grant_hash": purchase_grant_hash,
        "sku": SKU,
        "buyer_actor_id": norm["buyer_actor_id"],
        "conversation_id": norm["conversation_id"],
        "turn_index": norm["turn_index"],
        "entitlement_nonce": entitlement_nonce,
        "message_text": norm["message_text"],
        "message_hash": message_hash,
        "query_id": query_id,
        "conversation_history": [],
        "requested_output": {"mode": "JANUS_READ_ONLY_CONVERSATION"},
        "created_at": norm["created_at"],
    }
    query["query_hash"] = digest(query)
    packet = {
        "schema": PACKET_SCHEMA,
        "market_repository": MARKET_REPOSITORY,
        "home_repository": HOME_REPOSITORY,
        "transport_mode": "PHYSARIUS_CREDENTIALLESS_PULL",
        "mode": "PAID_ERC20",
        "request_origin": norm["request_origin"],
        "request_id": norm["request_id"],
        "request_hash": request_hash,
        "offer": offer,
        "offer_hash": offer_hash,
        "payment_receipt": payment_receipt,
        "payment_receipt_hash": payment_receipt_hash,
        "purchase_grant": grant,
        "purchase_grant_hash": purchase_grant_hash,
        "buyer_query": query,
        "query_id": query_id,
        "query_hash": query["query_hash"],
        "return_route": {
            "repository": MARKET_REPOSITORY,
            "source_issue_number": norm["source_issue_number"],
            "source_issue_id": norm["source_issue_id"],
        },
        "money_enabled": True,
        "payment_required": True,
        "production_purchase": True,
        "execution_authority_granted": False,
        "command_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "scientific_evidence_authority_granted": False,
        "world_truth_authority_granted": False,
        "laws": [
            "MARKET_IS_EXTERNAL_NERVE_NOT_JANUS_ROOT",
            "EVERY_EXTERNAL_NERVE -> HOME -> ACTIVATOR -> JANUS",
            "PAYMENT != COMMAND",
            "PAYMENT != EXECUTION_AUTHORITY",
            "PURCHASE_GRANT != EXECUTION_AUTHORITY",
            "BUYER_QUERY != COMMAND",
            "PHYSARIUS_DELIVERY != AUTHORITY",
            "ONE_PAYMENT_REFERENCE -> AT_MOST_ONE_PURCHASE_IDENTITY",
            "EXACT_RETRY != SECOND_COGNITION",
        ],
    }
    packet["packet_hash"] = digest(packet)
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a paid JANUS Machine Market -> HOME buyer-query packet")
    parser.add_argument("--request", required=True)
    parser.add_argument("--price", required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--payment-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    price = json.loads(Path(args.price).read_text(encoding="utf-8"))
    route = json.loads(Path(args.route).read_text(encoding="utf-8"))
    payment = json.loads(Path(args.payment_receipt).read_text(encoding="utf-8"))
    packet = build_paid_packet(request, price=price, route=route, payment_receipt=payment)
    Path(args.output).write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("R2_PAID_PACKET_BUILT=PASS")
    print("PURCHASE_ID=" + packet["purchase_grant"]["purchase_id"])
    print("QUERY_ID=" + packet["query_id"])
    print("PAYMENT_REFERENCE=" + packet["payment_receipt"]["payment_reference"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
