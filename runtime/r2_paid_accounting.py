#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from runtime.buyer_accounts import append_event, build_event, profile_id
from runtime.fulfillment_debt import open_debt, transition, verify as verify_debt


class PaidAccountingError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PaidAccountingError(code)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    text = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_account_event(
    *,
    ledger: Path,
    buyer_actor_id: str,
    event_type: str,
    event_id: str,
    created_at: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    existing = _read_events(ledger)
    previous = existing[-1]["event_hash"] if existing else None
    event = build_event(
        buyer_actor_id=buyer_actor_id,
        event_type=event_type,
        event_id=event_id,
        created_at=created_at,
        payload=payload,
        previous_event_hash=previous,
    )
    match = next((row for row in existing if row.get("event_id") == event_id), None)
    if match is not None:
        require(match.get("buyer_actor_id") == buyer_actor_id, "PAID_ACCOUNT_EVENT_BUYER_CONFLICT")
        require(match.get("event_type") == event_type, "PAID_ACCOUNT_EVENT_TYPE_CONFLICT")
        require(match.get("payload") == payload, "PAID_ACCOUNT_EVENT_PAYLOAD_CONFLICT")
        event = match
    return append_event(ledger_path=ledger, event=event)


def _account_paths(state_root: Path, buyer_actor_id: str) -> tuple[Path, Path]:
    pid = profile_id(buyer_actor_id)
    base = state_root / "state/accounts" / pid
    return base / "ledger.jsonl", base / "HEAD.json"


def _write_create_only_json(path: Path, value: dict[str, Any], conflict_code: str) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_text(encoding="utf-8") == encoded, conflict_code)
    else:
        path.write_text(encoded, encoding="utf-8")


def account_binding_path(state_root: Path, purchase_id: str) -> Path:
    return state_root / "state/r2-paid/account-bindings" / f"{purchase_id}.json"


def admit_paid_purchase(*, packet: dict[str, Any], state_root: Path) -> dict[str, Any]:
    require(packet.get("schema") == "janus.machine_market.home_paid_buyer_query_packet.v1", "PAID_ACCOUNT_PACKET_SCHEMA_INVALID")
    require(packet.get("mode") == "PAID_ERC20", "PAID_ACCOUNT_PACKET_MODE_INVALID")
    require(packet.get("money_enabled") is True and packet.get("production_purchase") is True, "PAID_ACCOUNT_NOT_PRODUCTION_PURCHASE")
    query = packet.get("buyer_query") or {}
    payment = packet.get("payment_receipt") or {}
    grant = packet.get("purchase_grant") or {}
    actor = str(query.get("buyer_actor_id") or "").strip()
    purchase_id = str(grant.get("purchase_id") or "").strip()
    query_id = str(packet.get("query_id") or "").strip()
    created_at = str(query.get("created_at") or "").strip()
    sku = str(query.get("sku") or "").strip()
    payment_reference = str(payment.get("payment_reference") or "").strip()
    payment_receipt_hash = str(packet.get("payment_receipt_hash") or "").strip()
    packet_hash = str(packet.get("packet_hash") or "").strip()
    require(all((actor, purchase_id, query_id, created_at, sku, payment_reference)), "PAID_ACCOUNT_BINDING_MISSING")
    require(len(payment_receipt_hash) == 64 and len(packet_hash) == 64, "PAID_ACCOUNT_HASH_BINDING_INVALID")
    amount_atomic = payment.get("amount_atomic")
    require(isinstance(amount_atomic, int) and not isinstance(amount_atomic, bool) and amount_atomic > 0, "PAID_ACCOUNT_AMOUNT_INVALID")

    ledger, head_path = _account_paths(state_root, actor)
    if not ledger.exists():
        head = _append_account_event(
            ledger=ledger,
            buyer_actor_id=actor,
            event_type="ACCOUNT_OPENED",
            event_id="account-opened:" + profile_id(actor),
            created_at=created_at,
            payload={"source": "R2_PAID_PURCHASE"},
        )
        head_path.parent.mkdir(parents=True, exist_ok=True)
        head_path.write_text(json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    head = _append_account_event(
        ledger=ledger,
        buyer_actor_id=actor,
        event_type="PURCHASE_ADMITTED",
        event_id="purchase-admitted:" + purchase_id,
        created_at=created_at,
        payload={
            "sku": sku,
            "purchase_id": purchase_id,
            "query_id": query_id,
            "payment_reference": payment_reference,
            "payment_receipt_hash": payment_receipt_hash,
            "amount_atomic": amount_atomic,
            "asset": "USDT",
        },
    )

    debt = open_debt(
        purchase_id=purchase_id,
        query_id=query_id,
        buyer_actor_id=actor,
        sku=sku,
        created_at=created_at,
    )
    debt_dir = state_root / "state/r2-paid/service-debts"
    debt_dir.mkdir(parents=True, exist_ok=True)
    debt_path = debt_dir / f"{debt['service_debt_id']}.json"
    if debt_path.exists():
        existing_debt = json.loads(debt_path.read_text(encoding="utf-8"))
        require(verify_debt(existing_debt), "PAID_EXISTING_SERVICE_DEBT_INVALID")
        require(existing_debt["purchase_id"] == purchase_id and existing_debt["query_id"] == query_id, "PAID_SERVICE_DEBT_CONFLICT")
        debt = existing_debt
    else:
        debt_path.write_text(json.dumps(debt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    binding = {
        "schema": "janus.machine_market.r2_paid_account_binding.v1",
        "profile_id": profile_id(actor),
        "buyer_actor_id": actor,
        "purchase_id": purchase_id,
        "query_id": query_id,
        "sku": sku,
        "amount_atomic": amount_atomic,
        "asset": "USDT",
        "payment_reference": payment_reference,
        "payment_receipt_hash": payment_receipt_hash,
        "packet_hash": packet_hash,
        "service_debt_id": debt["service_debt_id"],
        "source_issue_number": (packet.get("return_route") or {}).get("source_issue_number"),
        "source_issue_id": (packet.get("return_route") or {}).get("source_issue_id"),
        "created_at": created_at,
    }
    binding["binding_hash"] = _digest(binding)
    _write_create_only_json(
        account_binding_path(state_root, purchase_id),
        binding,
        "PAID_ACCOUNT_BINDING_CREATE_ONLY_CONFLICT",
    )

    head = _append_account_event(
        ledger=ledger,
        buyer_actor_id=actor,
        event_type="SERVICE_DEBT_OPENED",
        event_id="service-debt-opened:" + debt["service_debt_id"],
        created_at=created_at,
        payload={
            "service_debt_id": debt["service_debt_id"],
            "purchase_id": purchase_id,
            "query_id": query_id,
            "sku": sku,
        },
    )
    head_path.write_text(json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema": "janus.machine_market.r2_paid_account_admission.v1",
        "profile_id": profile_id(actor),
        "buyer_actor_id": actor,
        "purchase_id": purchase_id,
        "query_id": query_id,
        "service_debt_id": debt["service_debt_id"],
        "service_debt_state": debt["state"],
        "account_binding_hash": binding["binding_hash"],
        "account_head_hash": head["head_hash"],
        "open_service_debt_count": head["open_service_debt_count"],
        "payment_is_command": False,
        "payment_is_execution_authority": False,
    }


def mark_outbox_published(*, state_root: Path, service_debt_id: str, packet_hash: str, at: str) -> dict[str, Any]:
    path = state_root / "state/r2-paid/service-debts" / f"{service_debt_id}.json"
    require(path.exists(), "PAID_SERVICE_DEBT_MISSING_FOR_OUTBOX")
    debt = json.loads(path.read_text(encoding="utf-8"))
    if debt.get("state") == "SERVICE_DEBT_OPEN":
        debt = transition(debt, event="OUTBOX_PUBLISHED", at=at, binding=packet_hash)
        path.write_text(json.dumps(debt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        require(debt.get("outbox_packet_hash") == packet_hash, "PAID_OUTBOX_DEBT_BINDING_CONFLICT")
    return debt


def _load_account_binding(state_root: Path, purchase_id: str) -> dict[str, Any]:
    path = account_binding_path(state_root, purchase_id)
    require(path.exists(), "PAID_DELIVERY_ACCOUNT_BINDING_MISSING")
    binding = json.loads(path.read_text(encoding="utf-8"))
    require(binding.get("schema") == "janus.machine_market.r2_paid_account_binding.v1", "PAID_DELIVERY_ACCOUNT_BINDING_SCHEMA_INVALID")
    body = dict(binding)
    claimed = str(body.pop("binding_hash", ""))
    require(len(claimed) == 64 and _digest(body) == claimed, "PAID_DELIVERY_ACCOUNT_BINDING_HASH_INVALID")
    require(binding.get("purchase_id") == purchase_id, "PAID_DELIVERY_ACCOUNT_BINDING_PURCHASE_MISMATCH")
    return binding


def reconcile_delivery(
    *,
    response: dict[str, Any],
    state_root: Path,
    buyer_delivery_receipt_hash: str,
    delivered_at: str,
    reward_policy: dict[str, Any],
) -> dict[str, Any]:
    qid = str(response.get("query_id") or "")
    purchase_id = str(response.get("purchase_id") or "")
    payment_reference = str(response.get("payment_reference") or "")
    require(all((qid, purchase_id, payment_reference, buyer_delivery_receipt_hash, delivered_at)), "PAID_DELIVERY_BINDING_MISSING")

    claim_key = hashlib.sha256(payment_reference.encode("utf-8")).hexdigest()
    claim_path = state_root / "state/r2-paid/payment-claims" / f"{claim_key}.json"
    require(claim_path.exists(), "PAID_DELIVERY_PAYMENT_CLAIM_MISSING")
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    require(claim.get("payment_reference") == payment_reference, "PAID_DELIVERY_PAYMENT_REFERENCE_MISMATCH")
    require(claim.get("purchase_id") == purchase_id and claim.get("query_id") == qid, "PAID_DELIVERY_CLAIM_IDENTITY_MISMATCH")

    binding = _load_account_binding(state_root, purchase_id)
    require(binding.get("payment_reference") == payment_reference, "PAID_DELIVERY_ACCOUNT_PAYMENT_MISMATCH")
    require(binding.get("query_id") == qid, "PAID_DELIVERY_ACCOUNT_QUERY_MISMATCH")
    require(binding.get("payment_receipt_hash") == claim.get("payment_receipt_hash"), "PAID_DELIVERY_ACCOUNT_RECEIPT_MISMATCH")
    require(binding.get("packet_hash") == claim.get("packet_hash"), "PAID_DELIVERY_ACCOUNT_PACKET_MISMATCH")

    actor = str(binding["buyer_actor_id"])
    amount_atomic = binding["amount_atomic"]
    sku = str(binding["sku"])
    service_debt_id = str(binding["service_debt_id"])
    require(isinstance(amount_atomic, int) and amount_atomic > 0, "PAID_DELIVERY_AMOUNT_INVALID")

    debt_path = state_root / "state/r2-paid/service-debts" / f"{service_debt_id}.json"
    require(debt_path.exists(), "PAID_DELIVERY_SERVICE_DEBT_MISSING")
    debt = json.loads(debt_path.read_text(encoding="utf-8"))
    result_identity = str((response.get("buyer_query_receipt") or {}).get("execution_identity") or "")
    market_receipt_hash = str(response.get("home_response_hash") or "")
    require(result_identity and len(market_receipt_hash) == 64, "PAID_DELIVERY_RESULT_BINDING_INVALID")
    if debt.get("closed") is not True:
        if debt["state"] == "OUTBOX_PUBLISHED":
            debt = transition(debt, event="HOME_ACCEPTED", at=delivered_at)
        if debt["state"] == "HOME_ACCEPTED":
            debt = transition(debt, event="JANUS_RESULT_SEALED", at=delivered_at, binding=result_identity)
        if debt["state"] == "JANUS_RESULT_SEALED":
            debt = transition(debt, event="MARKET_RECONCILED", at=delivered_at, binding=market_receipt_hash)
        if debt["state"] == "MARKET_RECONCILED":
            debt = transition(debt, event="BUYER_DELIVERED", at=delivered_at, binding=buyer_delivery_receipt_hash)
        debt_path.write_text(json.dumps(debt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    require(debt.get("closed") is True and debt.get("close_reason") == "VERIFIED_BUYER_DELIVERY", "PAID_DELIVERY_DEBT_NOT_CLOSED")

    ledger, head_path = _account_paths(state_root, actor)
    head = _append_account_event(
        ledger=ledger,
        buyer_actor_id=actor,
        event_type="SERVICE_DELIVERED",
        event_id="service-delivered:" + service_debt_id,
        created_at=delivered_at,
        payload={
            "service_debt_id": service_debt_id,
            "purchase_id": purchase_id,
            "query_id": qid,
            "execution_identity": result_identity,
            "buyer_delivery_receipt_hash": buyer_delivery_receipt_hash,
        },
    )
    reward = reward_policy.get("production_purchase_reward") or {}
    require(reward.get("mint_trigger") in (None, "VERIFIED_BUYER_DELIVERY"), "JANUS_COIN_MINT_TRIGGER_INVALID")
    divisor = int(reward.get("usdt_atomic_per_coin", 1000))
    require(divisor > 0, "JANUS_COIN_REWARD_DIVISOR_INVALID")
    coins = amount_atomic // divisor
    if coins > 0:
        head = _append_account_event(
            ledger=ledger,
            buyer_actor_id=actor,
            event_type="JANUS_COIN_MINTED",
            event_id="janus-coin-purchase-reward:" + purchase_id,
            created_at=delivered_at,
            payload={
                "amount": coins,
                "purchase_id": purchase_id,
                "sku": sku,
                "verified_paid_usdt_atomic": amount_atomic,
                "reward_policy": reward_policy.get("schema"),
            },
        )
    head_path.write_text(json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema": "janus.machine_market.r2_paid_delivery_accounting.v1",
        "profile_id": profile_id(actor),
        "buyer_actor_id": actor,
        "purchase_id": purchase_id,
        "query_id": qid,
        "service_debt_id": service_debt_id,
        "service_debt_closed": True,
        "janus_coin_minted": coins,
        "janus_coin_balance": head["balances"]["JANUS_COIN"],
        "fulfilled_count": head["fulfilled_count"],
        "open_service_debt_count": head["open_service_debt_count"],
        "account_head_hash": head["head_hash"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS R2 paid buyer accounting")
    sub = parser.add_subparsers(dest="cmd", required=True)
    admit = sub.add_parser("admit")
    admit.add_argument("--packet", required=True)
    admit.add_argument("--state-root", required=True)
    admit.add_argument("--output", required=True)
    outbox = sub.add_parser("outbox")
    outbox.add_argument("--state-root", required=True)
    outbox.add_argument("--service-debt-id", required=True)
    outbox.add_argument("--packet-hash", required=True)
    outbox.add_argument("--at", required=True)
    outbox.add_argument("--output", required=True)
    delivery = sub.add_parser("delivery")
    delivery.add_argument("--response", required=True)
    delivery.add_argument("--state-root", required=True)
    delivery.add_argument("--buyer-delivery-receipt-hash", required=True)
    delivery.add_argument("--delivered-at", required=True)
    delivery.add_argument("--reward-policy", default="JANUS_COIN_REWARD_POLICY.json")
    delivery.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.cmd == "admit":
        result = admit_paid_purchase(packet=json.loads(Path(args.packet).read_text(encoding="utf-8")), state_root=Path(args.state_root))
    elif args.cmd == "outbox":
        debt = mark_outbox_published(state_root=Path(args.state_root), service_debt_id=args.service_debt_id, packet_hash=args.packet_hash, at=args.at)
        result = {
            "schema": "janus.machine_market.r2_paid_outbox_accounting.v1",
            "service_debt_id": debt["service_debt_id"],
            "state": debt["state"],
            "packet_hash": debt["outbox_packet_hash"],
            "closed": debt["closed"],
        }
    else:
        result = reconcile_delivery(
            response=json.loads(Path(args.response).read_text(encoding="utf-8")),
            state_root=Path(args.state_root),
            buyer_delivery_receipt_hash=args.buyer_delivery_receipt_hash,
            delivered_at=args.delivered_at,
            reward_policy=json.loads(Path(args.reward_policy).read_text(encoding="utf-8")),
        )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
