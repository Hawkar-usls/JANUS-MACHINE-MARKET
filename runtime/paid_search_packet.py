#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

from runtime.commerce_authority import (
    PAID_SEARCH_HISTORY_TURNS,
    PAID_SEARCH_MAX_ANSWER_UTF8_BYTES,
    PAID_SEARCH_MAX_MESSAGE_UTF8_BYTES,
    PAID_SEARCH_MAX_TURNS,
    CommerceInvalid,
    digest,
    receipt_payment_reference,
    request_hash,
    verify_payment_receipt,
)

REQUEST_SCHEMA = "janus.machine_market.buyer_query_shadow_request.v1"
PACKET_SCHEMA = "janus.machine_market.home_buyer_query_packet.v1"
QUERY_SCHEMA = "janus.machine_market.buyer_query.v1"
GRANT_SCHEMA = "janus.machine_market.purchase_grant.v1"
PAID_MODE = "PAID_SETTLED"
PAID_ORIGIN = "FOREIGN_PAID_SEARCH"
SKU = "JANUS.SEARCH"
MARKET_REPOSITORY = "Hawkar-usls/JANUS-MACHINE-MARKET"
HOME_REPOSITORY = "Hawkar-usls/Hawkar-usls"


class PaidSearchPacketError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PaidSearchPacketError(code)


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_without(value: dict[str, Any], field: str) -> str:
    body=dict(value); body.pop(field, None); return digest(body)


def normalize_paid_issue_request(issue: dict[str, Any], raw: dict[str, Any], *, owner_login: str) -> dict[str, Any]:
    user=issue.get("user") or {}
    login=str(user.get("login") or "").strip()
    _require(bool(login), "PAID_SEARCH_GITHUB_LOGIN_REQUIRED")
    _require(login.lower() != str(owner_login).lower(), "PAID_SEARCH_OWNER_SELF_PAYMENT_FORBIDDEN")
    _require(raw.get("schema") == REQUEST_SCHEMA, "PAID_SEARCH_REQUEST_SCHEMA_INVALID")
    message=str(raw.get("message_text") or "").strip()
    _require(bool(message), "PAID_SEARCH_MESSAGE_REQUIRED")
    _require(len(message.encode("utf-8")) <= PAID_SEARCH_MAX_MESSAGE_UTF8_BYTES, "PAID_SEARCH_MESSAGE_TOO_LARGE")
    issue_id=int(issue.get("id") or 0); issue_number=int(issue.get("number") or 0)
    _require(issue_id > 0 and issue_number > 0, "PAID_SEARCH_ISSUE_IDENTITY_INVALID")
    created_at=str(issue.get("created_at") or "").strip()
    _require(bool(created_at), "PAID_SEARCH_CREATED_AT_REQUIRED")
    return {
        "schema": REQUEST_SCHEMA,
        "request_id": f"github-issue-id:{issue_id}",
        "sku": SKU,
        "buyer_actor_id": f"github:{login}",
        "conversation_id": f"paid-market-issue-{issue_id}",
        "turn_index": 0,
        "message_text": message,
        "created_at": created_at,
        "max_turns": PAID_SEARCH_MAX_TURNS,
        "max_message_utf8_bytes": PAID_SEARCH_MAX_MESSAGE_UTF8_BYTES,
        "max_answer_utf8_bytes": PAID_SEARCH_MAX_ANSWER_UTF8_BYTES,
        "conversation_history_turns": PAID_SEARCH_HISTORY_TURNS,
        "source_issue_number": issue_number,
        "source_issue_id": issue_id,
        "request_origin": PAID_ORIGIN,
    }


def validate_paid_purchase(*, request: dict[str, Any], purchase_grant: dict[str, Any], quote: dict[str, Any], payment_receipt: dict[str, Any]) -> None:
    _require(request.get("schema") == REQUEST_SCHEMA and request.get("sku") == SKU, "PAID_SEARCH_REQUEST_INVALID")
    _require(request.get("request_origin") == PAID_ORIGIN, "PAID_SEARCH_ORIGIN_INVALID")
    _require(purchase_grant.get("schema") == GRANT_SCHEMA, "PAID_SEARCH_GRANT_SCHEMA_INVALID")
    _require(purchase_grant.get("status") == "PURCHASE_SETTLED", "PAID_SEARCH_PURCHASE_NOT_SETTLED")
    _require(purchase_grant.get("sku") == SKU, "PAID_SEARCH_GRANT_SKU_INVALID")
    _require(purchase_grant.get("execution_authority_granted") is False, "PAID_SEARCH_PURCHASE_MUST_NOT_BE_EXECUTION_AUTHORITY")
    _require(purchase_grant.get("request_hash") == request_hash(request), "PAID_SEARCH_GRANT_REQUEST_HASH_MISMATCH")
    _require(purchase_grant.get("quote_hash") == quote.get("quote_hash"), "PAID_SEARCH_GRANT_QUOTE_MISMATCH")
    _require(purchase_grant.get("payment_reference") == receipt_payment_reference(payment_receipt), "PAID_SEARCH_GRANT_PAYMENT_MISMATCH")
    grant_hash=str(purchase_grant.get("grant_hash") or "")
    _require(len(grant_hash)==64 and _hash_without(purchase_grant,"grant_hash")==grant_hash, "PAID_SEARCH_GRANT_HASH_INVALID")
    ent=purchase_grant.get("buyer_query_entitlement")
    _require(isinstance(ent,dict) and ent.get("enabled") is True, "PAID_SEARCH_ENTITLEMENT_REQUIRED")
    _require(ent.get("buyer_actor_id") == request.get("buyer_actor_id"), "PAID_SEARCH_BUYER_BINDING_MISMATCH")
    _require(ent.get("max_turns") == PAID_SEARCH_MAX_TURNS, "PAID_SEARCH_TURN_CAP_INVALID")
    _require(ent.get("max_message_utf8_bytes") == PAID_SEARCH_MAX_MESSAGE_UTF8_BYTES, "PAID_SEARCH_MESSAGE_CAP_INVALID")
    _require(ent.get("max_answer_utf8_bytes") == PAID_SEARCH_MAX_ANSWER_UTF8_BYTES, "PAID_SEARCH_ANSWER_CAP_INVALID")
    _require(ent.get("conversation_history_turns") == PAID_SEARCH_HISTORY_TURNS, "PAID_SEARCH_HISTORY_CAP_INVALID")
    _require(ent.get("read_only_conversation") is True and ent.get("external_effect_authorized") is False, "PAID_SEARCH_ENTITLEMENT_AUTHORITY_INVALID")
    verify_payment_receipt(quote,payment_receipt)


def build_paid_home_packet(*, request: dict[str, Any], purchase_grant: dict[str, Any], quote: dict[str, Any], payment_receipt: dict[str, Any]) -> dict[str, Any]:
    validate_paid_purchase(request=request,purchase_grant=purchase_grant,quote=quote,payment_receipt=payment_receipt)
    entitlement=purchase_grant["buyer_query_entitlement"]
    message_hash=_text_hash(str(request["message_text"]))
    query_id="bq-"+digest({
        "purchase_id":purchase_grant["purchase_id"],
        "conversation_id":request["conversation_id"],
        "turn_index":request["turn_index"],
        "message_hash":message_hash,
        "entitlement_nonce":entitlement["entitlement_nonce"],
    })
    query={
        "schema":QUERY_SCHEMA,
        "purchase_id":purchase_grant["purchase_id"],
        "purchase_grant_hash":purchase_grant["grant_hash"],
        "sku":SKU,
        "buyer_actor_id":request["buyer_actor_id"],
        "conversation_id":request["conversation_id"],
        "turn_index":request["turn_index"],
        "entitlement_nonce":entitlement["entitlement_nonce"],
        "message_text":request["message_text"],
        "message_hash":message_hash,
        "query_id":query_id,
        "conversation_history":[],
        "requested_output":{"mode":"JANUS_READ_ONLY_CONVERSATION"},
        "created_at":request["created_at"],
    }
    query["query_hash"]=digest(query)
    offer={
        "schema":"janus.machine_market.paid_search_offer.v1",
        "sku":SKU,
        "quote_hash":quote["quote_hash"],
        "price":{"amount_usdt_micros":int(quote["amount_usdt_micros"]),"asset":"USDT","chain_id":1},
        "payment_required":True,
        "production_purchase":True,
        "buyer_query_turns":PAID_SEARCH_MAX_TURNS,
    }
    packet={
        "schema":PACKET_SCHEMA,
        "market_repository":MARKET_REPOSITORY,
        "home_repository":HOME_REPOSITORY,
        "transport_mode":"PHYSARIUS_CREDENTIALLESS_PULL",
        "mode":PAID_MODE,
        "request_origin":request["request_origin"],
        "request_id":request["request_id"],
        "request_hash":request_hash(request),
        "offer":offer,
        "offer_hash":digest(offer),
        "purchase_grant":purchase_grant,
        "purchase_grant_hash":purchase_grant["grant_hash"],
        "buyer_query":query,
        "query_id":query_id,
        "query_hash":query["query_hash"],
        "return_route":{
            "repository":MARKET_REPOSITORY,
            "source_issue_number":request.get("source_issue_number"),
            "source_issue_id":request.get("source_issue_id"),
        },
        "commerce":{
            "quote":quote,
            "quote_hash":quote["quote_hash"],
            "payment_receipt":payment_receipt,
            "payment_reference":receipt_payment_reference(payment_receipt),
            "settlement_verified":True,
        },
        "money_enabled":True,
        "payment_required":True,
        "production_purchase":True,
        "execution_authority_granted":False,
        "command_authority_granted":False,
        "external_effect_authorized":False,
        "physical_runtime_effect_authorized":False,
        "scientific_evidence_authority_granted":False,
        "world_truth_authority_granted":False,
        "laws":[
            "MARKET_IS_EXTERNAL_NERVE_NOT_JANUS_ROOT",
            "EVERY_EXTERNAL_NERVE -> HOME -> ACTIVATOR -> JANUS",
            "PAYMENT != COMMAND",
            "PURCHASE_GRANT != EXECUTION_AUTHORITY",
            "BUYER_QUERY != COMMAND",
            "PHYSARIUS_DELIVERY != AUTHORITY",
            "EXACT_RETRY != SECOND_COGNITION",
            "EXACT_RETRY != SECOND_CHARGE",
        ],
    }
    packet["packet_hash"]=digest(packet)
    return packet


def verify_paid_home_packet(packet: dict[str, Any]) -> bool:
    try:
        if packet.get("schema") != PACKET_SCHEMA or packet.get("mode") != PAID_MODE:
            return False
        body=dict(packet); claimed=str(body.pop("packet_hash", ""))
        if len(claimed)!=64 or digest(body)!=claimed:
            return False
        if packet.get("market_repository")!=MARKET_REPOSITORY or packet.get("home_repository")!=HOME_REPOSITORY:
            return False
        if packet.get("transport_mode")!="PHYSARIUS_CREDENTIALLESS_PULL":
            return False
        if packet.get("money_enabled") is not True or packet.get("payment_required") is not True or packet.get("production_purchase") is not True:
            return False
        if any(packet.get(k) is not False for k in ("execution_authority_granted","command_authority_granted","external_effect_authorized","physical_runtime_effect_authorized","scientific_evidence_authority_granted","world_truth_authority_granted")):
            return False
        grant=packet.get("purchase_grant"); query=packet.get("buyer_query"); commerce=packet.get("commerce")
        if not isinstance(grant,dict) or not isinstance(query,dict) or not isinstance(commerce,dict):
            return False
        validate_paid_purchase(request={
            "schema":REQUEST_SCHEMA,"request_id":packet["request_id"],"sku":SKU,"buyer_actor_id":query["buyer_actor_id"],"conversation_id":query["conversation_id"],"turn_index":query["turn_index"],"message_text":query["message_text"],"created_at":query["created_at"],"max_turns":grant["buyer_query_entitlement"]["max_turns"],"max_message_utf8_bytes":grant["buyer_query_entitlement"]["max_message_utf8_bytes"],"max_answer_utf8_bytes":grant["buyer_query_entitlement"]["max_answer_utf8_bytes"],"conversation_history_turns":grant["buyer_query_entitlement"]["conversation_history_turns"],"source_issue_number":packet["return_route"].get("source_issue_number"),"source_issue_id":packet["return_route"].get("source_issue_id"),"request_origin":packet["request_origin"]
        },purchase_grant=grant,quote=commerce["quote"],payment_receipt=commerce["payment_receipt"])
        if packet["purchase_grant_hash"]!=grant["grant_hash"] or packet["query_id"]!=query["query_id"] or packet["query_hash"]!=query["query_hash"]:
            return False
        q=dict(query); qh=str(q.pop("query_hash", ""))
        if digest(q)!=qh:
            return False
        return True
    except (KeyError,TypeError,ValueError,CommerceInvalid,PaidSearchPacketError):
        return False


__all__=["PAID_MODE","PAID_ORIGIN","PaidSearchPacketError","build_paid_home_packet","normalize_paid_issue_request","validate_paid_purchase","verify_paid_home_packet"]
