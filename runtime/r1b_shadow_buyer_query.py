#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUEST_SCHEMA = "janus.machine_market.buyer_query_shadow_request.v1"
GRANT_SCHEMA = "janus.machine_market.purchase_grant.v1"
QUERY_SCHEMA = "janus.machine_market.buyer_query.v1"
PACKET_SCHEMA = "janus.machine_market.home_buyer_query_packet.v1"
SKU = "JANUS.SEARCH"
MARKET_REPOSITORY = "Hawkar-usls/JANUS-MACHINE-MARKET"
HOME_REPOSITORY = "Hawkar-usls/Hawkar-usls"


class ShadowBuyerQueryError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ShadowBuyerQueryError(code)


def normalize_request(request: dict[str, Any]) -> dict[str, Any]:
    require(request.get("schema") == REQUEST_SCHEMA, "R1B_REQUEST_SCHEMA_INVALID")
    request_id = str(request.get("request_id") or "").strip()
    buyer_actor_id = str(request.get("buyer_actor_id") or "").strip()
    conversation_id = str(request.get("conversation_id") or "").strip()
    message_text = str(request.get("message_text") or "").strip()
    created_at = str(request.get("created_at") or "").strip()
    sku = str(request.get("sku") or SKU).strip()
    turn_index = request.get("turn_index", 0)
    max_turns = request.get("max_turns", 1)
    max_message = request.get("max_message_utf8_bytes", 8000)
    max_answer = request.get("max_answer_utf8_bytes", 12000)
    history_turns = request.get("conversation_history_turns", 8)

    require(bool(request_id), "R1B_REQUEST_ID_REQUIRED")
    require(sku == SKU, "R1B_ONLY_JANUS_SEARCH_ALLOWED")
    require(bool(buyer_actor_id), "R1B_BUYER_ACTOR_REQUIRED")
    require(bool(conversation_id), "R1B_CONVERSATION_ID_REQUIRED")
    require(isinstance(turn_index, int) and not isinstance(turn_index, bool) and turn_index >= 0, "R1B_TURN_INDEX_INVALID")
    require(isinstance(max_turns, int) and 1 <= max_turns <= 8, "R1B_MAX_TURNS_OUT_OF_RANGE")
    require(turn_index < max_turns, "R1B_TURN_BUDGET_EXHAUSTED")
    require(bool(message_text), "R1B_MESSAGE_REQUIRED")
    require(len(message_text.encode("utf-8")) <= 8000, "R1B_MESSAGE_TOO_LARGE")
    require(bool(created_at), "R1B_CREATED_AT_REQUIRED")
    require(isinstance(max_message, int) and 1 <= max_message <= 8000, "R1B_MESSAGE_LIMIT_INVALID")
    require(isinstance(max_answer, int) and 1 <= max_answer <= 12000, "R1B_ANSWER_LIMIT_INVALID")
    require(isinstance(history_turns, int) and 0 <= history_turns <= 8, "R1B_HISTORY_LIMIT_INVALID")
    require(len(message_text.encode("utf-8")) <= max_message, "R1B_MESSAGE_EXCEEDS_ENTITLEMENT")

    return {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "sku": SKU,
        "buyer_actor_id": buyer_actor_id,
        "conversation_id": conversation_id,
        "turn_index": turn_index,
        "message_text": message_text,
        "created_at": created_at,
        "max_turns": max_turns,
        "max_message_utf8_bytes": max_message,
        "max_answer_utf8_bytes": max_answer,
        "conversation_history_turns": history_turns,
        "source_issue_number": request.get("source_issue_number"),
        "source_issue_id": request.get("source_issue_id"),
        "request_origin": str(request.get("request_origin") or "SELF_OWNER_SHADOW"),
    }


def build_shadow_packet(request: dict[str, Any]) -> dict[str, Any]:
    norm = normalize_request(request)
    request_hash = digest(norm)
    offer = {
        "schema": "janus.machine_market.buyer_query_shadow_offer.v1",
        "sku": SKU,
        "mode": "ZERO_PRICE_SHADOW",
        "price": {"amount": "0", "asset": "NONE"},
        "payment_required": False,
        "production_purchase": False,
        "buyer_query_turns": norm["max_turns"],
    }
    offer_hash = digest(offer)
    purchase_id = "pur-bq-shadow-" + digest({
        "request_id": norm["request_id"],
        "request_hash": request_hash,
        "offer_hash": offer_hash,
    })[:32]
    entitlement_nonce = "shadow-" + digest({
        "purchase_id": purchase_id,
        "purpose": "R1B_ZERO_PRICE_BUYER_QUERY_ENTITLEMENT",
    })[:32]
    grant = {
        "schema": GRANT_SCHEMA,
        "purchase_id": purchase_id,
        "sku": SKU,
        "offer_hash": offer_hash,
        "request_hash": request_hash,
        "terms_hash": None,
        "payment_reference": None,
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
            "R1B_ZERO_PRICE_SHADOW",
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
        "mode": "ZERO_PRICE_SHADOW",
        "request_origin": norm["request_origin"],
        "request_id": norm["request_id"],
        "request_hash": request_hash,
        "offer": offer,
        "offer_hash": offer_hash,
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
        "money_enabled": False,
        "payment_required": False,
        "production_purchase": False,
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
            "PURCHASE_GRANT != EXECUTION_AUTHORITY",
            "BUYER_QUERY != COMMAND",
            "PHYSARIUS_DELIVERY != AUTHORITY",
            "EXACT_RETRY != SECOND_COGNITION",
        ],
    }
    packet["packet_hash"] = digest(packet)
    return packet


def verify_shadow_packet(packet: dict[str, Any]) -> bool:
    if not isinstance(packet, dict) or packet.get("schema") != PACKET_SCHEMA:
        return False
    value = dict(packet)
    claimed = str(value.pop("packet_hash", ""))
    if len(claimed) != 64 or digest(value) != claimed:
        return False
    if value.get("market_repository") != MARKET_REPOSITORY or value.get("home_repository") != HOME_REPOSITORY:
        return False
    if value.get("mode") != "ZERO_PRICE_SHADOW" or value.get("money_enabled") is not False:
        return False
    if any(value.get(k) is not False for k in (
        "payment_required", "production_purchase", "execution_authority_granted",
        "command_authority_granted", "external_effect_authorized",
        "physical_runtime_effect_authorized", "scientific_evidence_authority_granted",
        "world_truth_authority_granted",
    )):
        return False
    grant = value.get("purchase_grant")
    query = value.get("buyer_query")
    if not isinstance(grant, dict) or not isinstance(query, dict):
        return False
    if digest(grant) != value.get("purchase_grant_hash"):
        return False
    if grant.get("execution_authority_granted") is not False:
        return False
    entitlement = grant.get("buyer_query_entitlement")
    if not isinstance(entitlement, dict) or entitlement.get("enabled") is not True:
        return False
    if entitlement.get("read_only_conversation") is not True or entitlement.get("external_effect_authorized") is not False:
        return False
    if query.get("purchase_id") != grant.get("purchase_id"):
        return False
    if query.get("purchase_grant_hash") != value.get("purchase_grant_hash"):
        return False
    if query.get("buyer_actor_id") != entitlement.get("buyer_actor_id"):
        return False
    q = dict(query)
    query_hash = str(q.pop("query_hash", ""))
    if len(query_hash) != 64 or digest(q) != query_hash:
        return False
    if query_hash != value.get("query_hash") or query.get("query_id") != value.get("query_id"):
        return False
    message_hash = digest(str(query.get("message_text") or ""))
    if message_hash != query.get("message_hash"):
        return False
    expected_qid = "bq-" + digest({
        "purchase_id": query.get("purchase_id"),
        "conversation_id": query.get("conversation_id"),
        "turn_index": query.get("turn_index"),
        "message_hash": query.get("message_hash"),
        "entitlement_nonce": query.get("entitlement_nonce"),
    })
    return expected_qid == query.get("query_id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a zero-price JANUS Machine Market -> HOME buyer-query shadow packet")
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    packet = build_shadow_packet(request)
    if not verify_shadow_packet(packet):
        raise SystemExit("R1B_SHADOW_PACKET_SELF_VERIFY_FAILED")
    text = json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
