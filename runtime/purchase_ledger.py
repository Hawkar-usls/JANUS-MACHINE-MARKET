"""Create-only persistent purchase ledger for JANUS MACHINE MARKET.

Designed for a mounted `janus/market-state` worktree protected by the shared
`janus-machine-market-state-writer` workflow concurrency group. Local filesystem
writes are also O_EXCL/create-only so exact retries are idempotent and conflicting
replays fail closed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from runtime.commerce_authority import CommerceInvalid, digest, receipt_payment_reference


class LedgerConflict(RuntimeError): pass


def _pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _create_only(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); payload = _pretty(value)
    try: fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() == payload: return "IDEMPOTENT_REPLAY"
        raise LedgerConflict(f"conflicting create-only record: {path}")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload); fh.flush(); os.fsync(fh.fileno())
    except Exception:
        try: path.unlink(missing_ok=True)
        finally: raise
    return "CREATED"


def payment_key(payment_reference: str) -> str: return digest({"payment_reference": str(payment_reference).lower()})


def persist_purchase(state_root: str | Path, payment_receipt: dict[str, Any], purchase_grant: dict[str, Any]) -> dict[str, str]:
    state_root = Path(state_root); ref = receipt_payment_reference(payment_receipt)
    if purchase_grant.get("payment_reference") != ref: raise CommerceInvalid("purchase grant/payment receipt reference mismatch")
    if not purchase_grant.get("purchase_id"): raise CommerceInvalid("purchase grant missing purchase_id")
    if purchase_grant.get("execution_authority_granted") is not False: raise CommerceInvalid("purchase ledger refuses a grant that claims execution authority")
    if purchase_grant.get("status") != "PURCHASE_SETTLED": raise CommerceInvalid("purchase ledger requires settled purchase grant")

    payment_record = {
        "schema": "janus.machine_market.payment_ledger_record.v1", "payment_reference": ref,
        "payment_receipt": payment_receipt, "purchase_id": purchase_grant["purchase_id"],
        "purchase_grant_hash": purchase_grant.get("grant_hash"),
    }
    purchase_record = {
        "schema": "janus.machine_market.purchase_ledger_record.v1", "purchase_id": purchase_grant["purchase_id"],
        "payment_reference": ref, "purchase_grant": purchase_grant,
        "execution_receipt": None, "billable_execution_identity": None,
    }
    payment_path = state_root / "state/commerce/payments" / f"{payment_key(ref)}.json"
    purchase_path = state_root / "state/commerce/purchases" / f"{purchase_grant['purchase_id']}.json"
    payment_status = _create_only(payment_path, payment_record)
    try: purchase_status = _create_only(purchase_path, purchase_record)
    except Exception:
        if payment_status == "CREATED": payment_path.unlink(missing_ok=True)
        raise
    return {"payment": payment_status, "purchase": purchase_status, "payment_path": str(payment_path), "purchase_path": str(purchase_path)}


def consumed_payment_references(state_root: str | Path) -> set[str]:
    root = Path(state_root) / "state/commerce/payments"; refs: set[str] = set()
    if not root.is_dir(): return refs
    for path in root.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8")); ref = str(row.get("payment_reference") or "").lower()
            if ref: refs.add(ref)
        except Exception as exc: raise LedgerConflict(f"invalid persistent payment ledger record: {path}") from exc
    return refs
