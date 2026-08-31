#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "janus.machine_market.fulfillment_debt.v1"


class FulfillmentDebtError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(cond: bool, code: str) -> None:
    if not cond:
        raise FulfillmentDebtError(code)


def open_debt(*, purchase_id: str, query_id: str, buyer_actor_id: str, sku: str, created_at: str) -> dict[str, Any]:
    core = {
        "purchase_id": purchase_id,
        "query_id": query_id,
        "buyer_actor_id": buyer_actor_id,
        "sku": sku,
    }
    debt = {
        "schema": SCHEMA,
        "service_debt_id": "debt-" + digest(core),
        **core,
        "state": "SERVICE_DEBT_OPEN",
        "created_at": created_at,
        "updated_at": created_at,
        "outbox_packet_hash": None,
        "home_result_identity": None,
        "market_receipt_hash": None,
        "buyer_delivery_receipt_hash": None,
        "retry_count": 0,
        "closed": False,
        "close_reason": None,
    }
    debt["debt_hash"] = digest(debt)
    return debt


def verify(debt: dict[str, Any]) -> bool:
    if not isinstance(debt, dict) or debt.get("schema") != SCHEMA:
        return False
    value = dict(debt)
    claimed = str(value.pop("debt_hash", ""))
    if len(claimed) != 64 or digest(value) != claimed:
        return False
    expected = "debt-" + digest({
        "purchase_id": value.get("purchase_id"),
        "query_id": value.get("query_id"),
        "buyer_actor_id": value.get("buyer_actor_id"),
        "sku": value.get("sku"),
    })
    return value.get("service_debt_id") == expected


def transition(debt: dict[str, Any], *, event: str, at: str, binding: str | None = None) -> dict[str, Any]:
    require(verify(debt), "SERVICE_DEBT_INVALID")
    require(debt.get("closed") is False, "SERVICE_DEBT_ALREADY_CLOSED")
    current = debt["state"]
    allowed = {
        ("SERVICE_DEBT_OPEN", "OUTBOX_PUBLISHED"): "OUTBOX_PUBLISHED",
        ("OUTBOX_PUBLISHED", "HOME_ACCEPTED"): "HOME_ACCEPTED",
        ("HOME_ACCEPTED", "JANUS_RESULT_SEALED"): "JANUS_RESULT_SEALED",
        ("JANUS_RESULT_SEALED", "MARKET_RECONCILED"): "MARKET_RECONCILED",
        ("MARKET_RECONCILED", "BUYER_DELIVERED"): "BUYER_DELIVERED",
    }
    out = dict(debt)
    if event == "RETRY_PENDING":
        out["retry_count"] = int(out.get("retry_count", 0)) + 1
        out["updated_at"] = at
    elif event == "WORKFLOW_FAILURE" or event == "TIMEOUT" or event == "TRANSPORT_DEGRADED":
        out["state"] = current
        out["retry_count"] = int(out.get("retry_count", 0)) + 1
        out["updated_at"] = at
    else:
        target = allowed.get((current, event))
        require(target is not None, "SERVICE_DEBT_TRANSITION_FORBIDDEN")
        out["state"] = target
        out["updated_at"] = at
        if event == "OUTBOX_PUBLISHED":
            require(bool(binding), "OUTBOX_PACKET_HASH_REQUIRED")
            out["outbox_packet_hash"] = binding
        elif event == "JANUS_RESULT_SEALED":
            require(bool(binding), "HOME_RESULT_IDENTITY_REQUIRED")
            out["home_result_identity"] = binding
        elif event == "MARKET_RECONCILED":
            require(bool(binding), "MARKET_RECEIPT_HASH_REQUIRED")
            out["market_receipt_hash"] = binding
        elif event == "BUYER_DELIVERED":
            require(bool(binding), "BUYER_DELIVERY_RECEIPT_HASH_REQUIRED")
            out["buyer_delivery_receipt_hash"] = binding
            out["closed"] = True
            out["close_reason"] = "VERIFIED_BUYER_DELIVERY"
            out["state"] = "SERVICE_DEBT_CLOSED"
    out.pop("debt_hash", None)
    out["debt_hash"] = digest(out)
    return out


__all__ = ["FulfillmentDebtError", "open_debt", "transition", "verify"]
