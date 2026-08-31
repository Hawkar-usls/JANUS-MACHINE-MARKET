#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

QUOTE_REQUEST_SCHEMA = "janus.machine_market.quote_request.v1"
QUOTE_SCHEMA = "janus.machine_market.quote.v1"
SKU = "JANUS.SEARCH"


class QuoteError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise QuoteError(code)


def build_quote(request: dict[str, Any], *, price: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    require(request.get("schema") == QUOTE_REQUEST_SCHEMA, "R2_QUOTE_REQUEST_SCHEMA_INVALID")
    require(request.get("sku") == SKU, "R2_QUOTE_SKU_INVALID")
    request_id = str(request.get("request_id") or "").strip()
    buyer_actor_id = str(request.get("buyer_actor_id") or "").strip()
    input_value = request.get("input")
    require(bool(request_id), "R2_QUOTE_REQUEST_ID_REQUIRED")
    require(bool(buyer_actor_id), "R2_QUOTE_BUYER_REQUIRED")
    require(isinstance(input_value, dict), "R2_QUOTE_INPUT_REQUIRED")
    message = str(input_value.get("message_text") or "").strip()
    require(bool(message), "R2_QUOTE_MESSAGE_REQUIRED")
    require(len(message.encode("utf-8")) <= 8000, "R2_QUOTE_MESSAGE_TOO_LARGE")
    require(price.get("schema") == "janus.machine_market.price.v1" and price.get("sku") == SKU, "R2_QUOTE_PRICE_MANIFEST_INVALID")
    require(route.get("schema") == "janus.machine_market.payment_route.v1", "R2_QUOTE_PAYMENT_ROUTE_INVALID")

    normalized_request = {
        "schema": QUOTE_REQUEST_SCHEMA,
        "sku": SKU,
        "buyer_actor_id": buyer_actor_id,
        "request_id": request_id,
        "input": {
            "message_text": message,
            "conversation_id": input_value.get("conversation_id"),
            "turn_index": int(input_value.get("turn_index", 0)),
        },
        "created_at": request.get("created_at"),
    }
    request_hash = digest(normalized_request)

    price_live = (
        price.get("status") == "PUBLISHED"
        and price.get("machine_purchase_enabled") is True
        and isinstance(price.get("amount_atomic"), int)
        and not isinstance(price.get("amount_atomic"), bool)
        and price.get("amount_atomic") > 0
    )
    route_live = route.get("live_payment_enabled") is True
    if not price_live or not route_live:
        quote = {
            "schema": QUOTE_SCHEMA,
            "quote_id": "quote-blocked-" + digest({"request_hash": request_hash, "sku": SKU})[:32],
            "request_id": request_id,
            "sku": SKU,
            "status": "UNAVAILABLE",
            "price": None,
            "offer_hash": digest({"sku": SKU, "status": "UNAVAILABLE", "request_hash": request_hash}),
            "request_hash": request_hash,
            "terms_hash": None,
            "expires_at": None,
            "payment_challenge": None,
            "reasons": [
                "PRICE_NOT_PUBLISHED" if not price_live else "PRICE_READY",
                "PAYMENT_ROUTE_NOT_LIVE" if not route_live else "PAYMENT_ROUTE_READY",
            ],
        }
        return quote

    amount_atomic = int(price["amount_atomic"])
    price_body = {
        "asset": "USDT",
        "network": "ethereum-mainnet",
        "chain_id": 1,
        "amount_atomic": amount_atomic,
        "decimals": 6,
    }
    offer = {
        "sku": SKU,
        "request_hash": request_hash,
        "price": price_body,
        "price_manifest_hash": digest(price),
        "payment_route_id": route["route_id"],
        "buyer_query_turns": int(price.get("buyer_query_turns", 1)),
    }
    offer_hash = digest(offer)
    quote_id = "quote-" + digest({
        "request_id": request_id,
        "request_hash": request_hash,
        "offer_hash": offer_hash,
        "buyer_actor_id": buyer_actor_id,
    })[:40]
    terms_hash = digest({
        "payment_policy": "PAYMENT_POLICY.md",
        "purchase_protocol": "PURCHASE_PROTOCOL.json",
        "price_manifest_hash": offer["price_manifest_hash"],
        "payment_route_id": route["route_id"],
    })
    return {
        "schema": QUOTE_SCHEMA,
        "quote_id": quote_id,
        "request_id": request_id,
        "sku": SKU,
        "status": "QUOTED",
        "price": price_body,
        "offer_hash": offer_hash,
        "request_hash": request_hash,
        "terms_hash": terms_hash,
        "expires_at": None,
        "payment_challenge": {
            "mode": "ERC20_TRANSFER",
            "route_id": route["route_id"],
            "chain_id": 1,
            "asset": "USDT",
            "token_contract": route["asset"]["contract"],
            "to_address": route["merchant"]["receiving_address"],
            "amount_atomic": amount_atomic,
            "decimals": 6,
            "minimum_confirmations": int(route["verification"]["minimum_confirmations"]),
            "after_payment": {
                "title_prefix": "[JANUS PAID SEARCH]",
                "required_fields": ["tx_hash", "message_text"],
                "request_schema": "janus.machine_market.paid_buyer_query_request.v1"
            }
        },
        "reasons": [
            "BOUND_QUOTE_ONLY",
            "QUOTE_IS_NOT_PAYMENT",
            "QUOTE_IS_NOT_PURCHASE_GRANT",
            "PAYMENT_IS_NOT_EXECUTION_AUTHORITY"
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic JANUS Machine Market quote")
    parser.add_argument("--request", required=True)
    parser.add_argument("--price", required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    price = json.loads(Path(args.price).read_text(encoding="utf-8"))
    route = json.loads(Path(args.route).read_text(encoding="utf-8"))
    quote = build_quote(request, price=price, route=route)
    Path(args.output).write_text(json.dumps(quote, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("R2_QUOTE_STATUS=" + quote["status"])
    print("QUOTE_ID=" + quote["quote_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
