#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ACCOUNT_EVENT_SCHEMA = "janus.machine_market.buyer_account_event.v1"
ACCOUNT_HEAD_SCHEMA = "janus.machine_market.buyer_account_head.v1"


class BuyerAccountError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise BuyerAccountError(code)


def profile_id(buyer_actor_id: str) -> str:
    actor = str(buyer_actor_id or "").strip()
    require(bool(actor), "BUYER_ACTOR_ID_REQUIRED")
    return "buyer-" + digest(actor)


def build_event(
    *,
    buyer_actor_id: str,
    event_type: str,
    event_id: str,
    created_at: str,
    payload: dict[str, Any],
    previous_event_hash: str | None,
) -> dict[str, Any]:
    actor = str(buyer_actor_id or "").strip()
    etype = str(event_type or "").strip()
    eid = str(event_id or "").strip()
    created = str(created_at or "").strip()
    require(bool(actor), "BUYER_ACTOR_ID_REQUIRED")
    require(bool(etype), "ACCOUNT_EVENT_TYPE_REQUIRED")
    require(bool(eid), "ACCOUNT_EVENT_ID_REQUIRED")
    require(bool(created), "ACCOUNT_EVENT_TIME_REQUIRED")
    require(isinstance(payload, dict), "ACCOUNT_EVENT_PAYLOAD_REQUIRED")
    if previous_event_hash is not None:
        require(len(str(previous_event_hash)) == 64, "PREVIOUS_EVENT_HASH_INVALID")
    event = {
        "schema": ACCOUNT_EVENT_SCHEMA,
        "profile_id": profile_id(actor),
        "buyer_actor_id": actor,
        "event_type": etype,
        "event_id": eid,
        "created_at": created,
        "previous_event_hash": previous_event_hash,
        "payload": payload,
    }
    event["event_hash"] = digest(event)
    return event


def verify_event(event: dict[str, Any], *, expected_previous: str | None = None) -> bool:
    if not isinstance(event, dict):
        return False
    value = dict(event)
    claimed = str(value.pop("event_hash", ""))
    if len(claimed) != 64 or digest(value) != claimed:
        return False
    if value.get("schema") != ACCOUNT_EVENT_SCHEMA:
        return False
    actor = str(value.get("buyer_actor_id") or "").strip()
    if not actor or value.get("profile_id") != profile_id(actor):
        return False
    if expected_previous != value.get("previous_event_hash"):
        return False
    return True


def _empty_head(actor: str) -> dict[str, Any]:
    return {
        "schema": ACCOUNT_HEAD_SCHEMA,
        "profile_id": profile_id(actor),
        "buyer_actor_id": actor,
        "first_seen_at": None,
        "last_seen_at": None,
        "order_count": 0,
        "fulfilled_count": 0,
        "open_service_debt_count": 0,
        "sku_order_counts": {},
        "balances": {
            "MARKET_TEST_CREDIT": 0,
            "JANUS_COIN": 0,
            "SERVICE_CREDIT": 0
        },
        "janus_coin_earned_total": 0,
        "janus_coin_spent_total": 0,
        "review_count": 0,
        "last_event_hash": None,
        "event_count": 0,
    }


def project(events: list[dict[str, Any]]) -> dict[str, Any]:
    require(bool(events), "ACCOUNT_LEDGER_EMPTY")
    actor = str(events[0].get("buyer_actor_id") or "")
    head = _empty_head(actor)
    previous = None
    open_debts: set[str] = set()
    for event in events:
        require(event.get("buyer_actor_id") == actor, "ACCOUNT_LEDGER_MIXED_BUYERS")
        require(verify_event(event, expected_previous=previous), "ACCOUNT_EVENT_CHAIN_INVALID")
        previous = event["event_hash"]
        t = event["event_type"]
        p = event.get("payload") or {}
        created = event["created_at"]
        if head["first_seen_at"] is None:
            head["first_seen_at"] = created
        head["last_seen_at"] = created
        if t == "MARKET_TEST_CREDIT_MINTED":
            amount = int(p.get("amount", 0)); require(amount > 0, "TEST_CREDIT_MINT_INVALID")
            head["balances"]["MARKET_TEST_CREDIT"] += amount
        elif t == "MARKET_TEST_CREDIT_SPENT":
            amount = int(p.get("amount", 0)); require(amount > 0, "TEST_CREDIT_SPEND_INVALID")
            require(head["balances"]["MARKET_TEST_CREDIT"] >= amount, "TEST_CREDIT_BALANCE_INSUFFICIENT")
            head["balances"]["MARKET_TEST_CREDIT"] -= amount
        elif t == "PURCHASE_ADMITTED":
            sku = str(p.get("sku") or ""); require(bool(sku), "PURCHASE_SKU_REQUIRED")
            head["order_count"] += 1
            head["sku_order_counts"][sku] = int(head["sku_order_counts"].get(sku, 0)) + 1
        elif t == "SERVICE_DEBT_OPENED":
            debt_id = str(p.get("service_debt_id") or ""); require(bool(debt_id), "SERVICE_DEBT_ID_REQUIRED")
            require(debt_id not in open_debts, "SERVICE_DEBT_DUPLICATE_OPEN")
            open_debts.add(debt_id)
        elif t == "SERVICE_DELIVERED":
            debt_id = str(p.get("service_debt_id") or ""); require(debt_id in open_debts, "SERVICE_DELIVERY_WITHOUT_OPEN_DEBT")
            open_debts.remove(debt_id)
            head["fulfilled_count"] += 1
        elif t == "SERVICE_COMPENSATION_CREDITED":
            amount = int(p.get("amount", 0)); require(amount > 0, "SERVICE_CREDIT_INVALID")
            head["balances"]["SERVICE_CREDIT"] += amount
        elif t == "JANUS_COIN_MINTED":
            amount = int(p.get("amount", 0)); require(amount > 0, "JANUS_COIN_MINT_INVALID")
            head["balances"]["JANUS_COIN"] += amount
            head["janus_coin_earned_total"] += amount
        elif t == "JANUS_COIN_SPENT_GM_SHOP":
            amount = int(p.get("amount", 0)); require(amount > 0, "JANUS_COIN_SPEND_INVALID")
            require(head["balances"]["JANUS_COIN"] >= amount, "JANUS_COIN_BALANCE_INSUFFICIENT")
            head["balances"]["JANUS_COIN"] -= amount
            head["janus_coin_spent_total"] += amount
        elif t == "REVIEW_PUBLISHED":
            head["review_count"] += 1
        head["last_event_hash"] = event["event_hash"]
        head["event_count"] += 1
    head["open_service_debt_count"] = len(open_debts)
    head["head_hash"] = digest(head)
    return head


def append_event(*, ledger_path: Path, event: dict[str, Any]) -> dict[str, Any]:
    existing: list[dict[str, Any]] = []
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.append(json.loads(line))
    previous = existing[-1]["event_hash"] if existing else None
    require(event.get("previous_event_hash") == previous, "ACCOUNT_APPEND_PREVIOUS_HASH_MISMATCH")
    require(verify_event(event, expected_previous=previous), "ACCOUNT_APPEND_EVENT_INVALID")
    if any(row.get("event_id") == event.get("event_id") for row in existing):
        same = next(row for row in existing if row.get("event_id") == event.get("event_id"))
        require(same == event, "ACCOUNT_EVENT_ID_CREATE_ONLY_CONFLICT")
        return project(existing)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(canonical(event) + "\n")
    return project(existing + [event])


def main() -> int:
    parser = argparse.ArgumentParser(description="Append and project a JANUS buyer account event")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    head = append_event(ledger_path=Path(args.ledger), event=event)
    Path(args.head).parent.mkdir(parents=True, exist_ok=True)
    Path(args.head).write_text(json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(head, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
