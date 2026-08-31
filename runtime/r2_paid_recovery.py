#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from runtime.r2_paid_accounting import admit_paid_purchase, account_binding_path, mark_outbox_published, reconcile_delivery


class PaidRecoveryError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PaidRecoveryError(code)


def _claim_key(payment_reference: str) -> str:
    return hashlib.sha256(payment_reference.encode("utf-8")).hexdigest()


def _verify_packet_against_claim(packet: dict[str, Any], claim: dict[str, Any]) -> None:
    payment = packet.get("payment_receipt") or {}
    grant = packet.get("purchase_grant") or {}
    require(packet.get("schema") == "janus.machine_market.home_paid_buyer_query_packet.v1", "RECOVERY_PACKET_SCHEMA_INVALID")
    require(packet.get("mode") == "PAID_ERC20", "RECOVERY_PACKET_MODE_INVALID")
    require(packet.get("money_enabled") is True and packet.get("production_purchase") is True, "RECOVERY_PACKET_NOT_PRODUCTION_PAID")
    require(claim.get("schema") == "janus.machine_market.r2_payment_claim.v1", "RECOVERY_CLAIM_SCHEMA_INVALID")
    require(claim.get("payment_reference") == payment.get("payment_reference"), "RECOVERY_PAYMENT_REFERENCE_MISMATCH")
    require(claim.get("payment_receipt_hash") == packet.get("payment_receipt_hash"), "RECOVERY_PAYMENT_RECEIPT_HASH_MISMATCH")
    require(claim.get("purchase_id") == grant.get("purchase_id"), "RECOVERY_PURCHASE_ID_MISMATCH")
    require(claim.get("purchase_grant_hash") == packet.get("purchase_grant_hash"), "RECOVERY_GRANT_HASH_MISMATCH")
    require(claim.get("query_id") == packet.get("query_id"), "RECOVERY_QUERY_ID_MISMATCH")
    require(claim.get("query_hash") == packet.get("query_hash"), "RECOVERY_QUERY_HASH_MISMATCH")
    require(claim.get("packet_hash") == packet.get("packet_hash"), "RECOVERY_PACKET_HASH_MISMATCH")


def admit_from_witnesses(*, state_root: Path, outbox_root: Path, now: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    packet_dir = outbox_root / ".janus/market-home-outbox"
    for path in sorted(packet_dir.glob("*.paid.packet.json")) if packet_dir.exists() else []:
        packet = json.loads(path.read_text(encoding="utf-8"))
        payment_reference = str((packet.get("payment_receipt") or {}).get("payment_reference") or "")
        if not payment_reference:
            continue
        claim_path = state_root / "state/r2-paid/payment-claims" / f"{_claim_key(payment_reference)}.json"
        if not claim_path.exists():
            # A public outbox packet without the persistent claim cannot become
            # a buyer account obligation through recovery.
            continue
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        _verify_packet_against_claim(packet, claim)
        admission = admit_paid_purchase(packet=packet, state_root=state_root)
        debt = mark_outbox_published(
            state_root=state_root,
            service_debt_id=admission["service_debt_id"],
            packet_hash=str(packet["packet_hash"]),
            at=now,
        )
        results.append({
            "purchase_id": admission["purchase_id"],
            "query_id": admission["query_id"],
            "profile_id": admission["profile_id"],
            "service_debt_id": admission["service_debt_id"],
            "service_debt_state": debt["state"],
            "account_binding_hash": admission["account_binding_hash"],
        })
    return results


def close_from_delivery_proofs(
    *,
    state_root: Path,
    delivery_proofs: dict[str, Any],
    reward_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    closed: list[dict[str, Any]] = []
    results_dir = state_root / "state/r2-paid/results"
    if not results_dir.exists():
        return closed
    for result_path in sorted(results_dir.glob("*.json")):
        response = json.loads(result_path.read_text(encoding="utf-8"))
        qid = str(response.get("query_id") or "")
        purchase_id = str(response.get("purchase_id") or "")
        proof = delivery_proofs.get(qid)
        if not isinstance(proof, dict):
            continue
        require(proof.get("purchase_id") == purchase_id, "RECOVERY_DELIVERY_PROOF_PURCHASE_MISMATCH")
        receipt_hash = str(proof.get("buyer_delivery_receipt_hash") or "")
        delivered_at = str(proof.get("delivered_at") or "")
        require(len(receipt_hash) == 64 and bool(delivered_at), "RECOVERY_DELIVERY_PROOF_INVALID")
        require(account_binding_path(state_root, purchase_id).exists(), "RECOVERY_ACCOUNT_BINDING_MISSING")
        closed.append(reconcile_delivery(
            response=response,
            state_root=state_root,
            buyer_delivery_receipt_hash=receipt_hash,
            delivered_at=delivered_at,
            reward_policy=reward_policy,
        ))
    return closed


def run(*, state_root: Path, outbox_root: Path, delivery_proofs_path: Path | None, reward_policy_path: Path, now: str) -> dict[str, Any]:
    admitted = admit_from_witnesses(state_root=state_root, outbox_root=outbox_root, now=now)
    delivery_proofs: dict[str, Any] = {}
    if delivery_proofs_path is not None and delivery_proofs_path.exists():
        delivery_proofs = json.loads(delivery_proofs_path.read_text(encoding="utf-8"))
    reward_policy = json.loads(reward_policy_path.read_text(encoding="utf-8"))
    closed = close_from_delivery_proofs(state_root=state_root, delivery_proofs=delivery_proofs, reward_policy=reward_policy)
    open_debts = []
    debt_dir = state_root / "state/r2-paid/service-debts"
    for path in sorted(debt_dir.glob("*.json")) if debt_dir.exists() else []:
        debt = json.loads(path.read_text(encoding="utf-8"))
        if debt.get("closed") is not True:
            open_debts.append({
                "service_debt_id": debt.get("service_debt_id"),
                "purchase_id": debt.get("purchase_id"),
                "query_id": debt.get("query_id"),
                "state": debt.get("state"),
                "retry_count": debt.get("retry_count"),
            })
    return {
        "schema": "janus.machine_market.r2_paid_recovery_result.v1",
        "admitted_or_confirmed": admitted,
        "delivery_closed_or_confirmed": closed,
        "open_service_debts": open_debts,
        "open_service_debt_count": len(open_debts),
        "second_cognition_authorized": False,
        "payment_claim_mutated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover JANUS paid buyer accounting from create-only witnesses")
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--outbox-root", required=True)
    parser.add_argument("--delivery-proofs")
    parser.add_argument("--reward-policy", default="JANUS_COIN_REWARD_POLICY.json")
    parser.add_argument("--now", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(
        state_root=Path(args.state_root),
        outbox_root=Path(args.outbox_root),
        delivery_proofs_path=Path(args.delivery_proofs) if args.delivery_proofs else None,
        reward_policy_path=Path(args.reward_policy),
        now=args.now,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
