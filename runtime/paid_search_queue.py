#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from runtime.commerce_authority import CommerceInvalid, digest, parse_time, receipt_payment_reference
from runtime.paid_search_packet import verify_paid_home_packet

ENTRY_SCHEMA = "janus.machine_market.paid_search_queue_entry.v1"
ACTIVE_SCHEMA = "janus.machine_market.paid_search_queue_active.v1"
DISPATCH_SCHEMA = "janus.machine_market.paid_search_queue_dispatch.v1"
COMPLETION_SCHEMA = "janus.machine_market.paid_search_queue_completion.v1"
SNAPSHOT_SCHEMA = "janus.machine_market.paid_search_queue_snapshot.v1"


class QueueConflict(RuntimeError):
    pass


class QueueInvalid(ValueError):
    pass


def _pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _create_only(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _pretty(value)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() == payload:
            return "IDEMPOTENT_REPLAY"
        raise QueueConflict(f"conflicting create-only queue record: {path}")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    return "CREATED"


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise QueueInvalid(f"invalid queue json: {path}") from exc
    if not isinstance(value, dict):
        raise QueueInvalid(f"queue json must be object: {path}")
    return value


def queue_root(state_root: str | Path) -> Path:
    return Path(state_root) / "state/commerce/paid-search-queue"


def level_spec(policy: Mapping[str, Any], level: int) -> dict[str, Any]:
    levels = policy.get("levels") or {}
    spec = levels.get(str(int(level)))
    if not isinstance(spec, Mapping):
        raise QueueInvalid("QUEUE_LEVEL_INVALID")
    out = dict(spec)
    if int(level) < 1 or int(level) > int(policy.get("queue_levels", 0)):
        raise QueueInvalid("QUEUE_LEVEL_OUT_OF_RANGE")
    if int(out.get("price_multiplier_bps", 0)) < 10_000:
        raise QueueInvalid("QUEUE_LEVEL_MULTIPLIER_INVALID")
    return out


def effective_level(entry: Mapping[str, Any], policy: Mapping[str, Any], *, now: datetime) -> int:
    base = int(entry.get("queue_level", 0))
    level_spec(policy, base)
    aging = policy.get("aging") or {}
    if aging.get("enabled") is not True:
        return base
    step = int(aging.get("step_minutes", 0))
    if step <= 0:
        raise QueueInvalid("QUEUE_AGING_STEP_INVALID")
    max_boost = max(0, int(aging.get("max_boost_levels", 0)))
    paid_at = parse_time(str(entry.get("payment_block_timestamp") or ""))
    elapsed_minutes = max(0, int((now.astimezone(timezone.utc) - paid_at).total_seconds() // 60))
    boost = min(max_boost, elapsed_minutes // step)
    return min(int(policy.get("queue_levels", 5)), base + boost)


def build_queue_entry(
    *,
    request: Mapping[str, Any],
    purchase_grant: Mapping[str, Any],
    packet: Mapping[str, Any],
    payment_receipt: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    request = dict(request)
    purchase_grant = dict(purchase_grant)
    packet = dict(packet)
    payment_receipt = dict(payment_receipt)
    if not verify_paid_home_packet(packet):
        raise QueueInvalid("QUEUE_PACKET_INVALID")
    purchase_id = str(purchase_grant.get("purchase_id") or "")
    if not purchase_id or packet.get("purchase_grant", {}).get("purchase_id") != purchase_id:
        raise QueueInvalid("QUEUE_PURCHASE_BINDING_INVALID")
    if packet.get("purchase_grant_hash") != purchase_grant.get("grant_hash"):
        raise QueueInvalid("QUEUE_GRANT_HASH_MISMATCH")
    if packet.get("request_hash") != purchase_grant.get("request_hash"):
        raise QueueInvalid("QUEUE_REQUEST_HASH_MISMATCH")
    payment_ref = receipt_payment_reference(payment_receipt)
    if str(purchase_grant.get("payment_reference") or "").lower() != payment_ref:
        raise QueueInvalid("QUEUE_PAYMENT_REFERENCE_MISMATCH")
    level = int(request.get("queue_level", 1))
    spec = level_spec(policy, level)
    if int(request.get("queue_multiplier_bps", spec["price_multiplier_bps"])) != int(spec["price_multiplier_bps"]):
        raise QueueInvalid("QUEUE_MULTIPLIER_BINDING_MISMATCH")
    try:
        block_number = int(payment_receipt["block_number"])
        log_index = int(payment_receipt["log_index"])
    except (KeyError, TypeError, ValueError) as exc:
        raise QueueInvalid("QUEUE_PAYMENT_ORDERING_FIELDS_REQUIRED") from exc
    if block_number < 0 or log_index < 0:
        raise QueueInvalid("QUEUE_PAYMENT_ORDERING_FIELDS_INVALID")
    parse_time(str(payment_receipt.get("block_timestamp") or ""))
    body = {
        "schema": ENTRY_SCHEMA,
        "status": "QUEUED_PAID_SETTLED_NOT_STARTED",
        "sku": "JANUS.SEARCH",
        "purchase_id": purchase_id,
        "query_id": packet.get("query_id"),
        "request_hash": packet.get("request_hash"),
        "packet_hash": packet.get("packet_hash"),
        "buyer_actor_id": request.get("buyer_actor_id"),
        "source_issue_number": request.get("source_issue_number"),
        "source_issue_id": request.get("source_issue_id"),
        "queue_level": level,
        "queue_code": spec.get("code"),
        "queue_label": spec.get("label"),
        "queue_multiplier_bps": int(spec["price_multiplier_bps"]),
        "payment_reference": payment_ref,
        "payment_block_number": block_number,
        "payment_log_index": log_index,
        "payment_block_timestamp": payment_receipt.get("block_timestamp"),
        "preemptive": False,
        "packet": packet,
    }
    return {**body, "entry_hash": digest(body)}


def verify_queue_entry(entry: Mapping[str, Any], policy: Mapping[str, Any]) -> bool:
    try:
        value = dict(entry)
        claimed = str(value.pop("entry_hash", ""))
        if len(claimed) != 64 or digest(value) != claimed:
            return False
        if value.get("schema") != ENTRY_SCHEMA or value.get("status") != "QUEUED_PAID_SETTLED_NOT_STARTED":
            return False
        if value.get("sku") != "JANUS.SEARCH" or value.get("preemptive") is not False:
            return False
        spec = level_spec(policy, int(value.get("queue_level", 0)))
        if int(value.get("queue_multiplier_bps", 0)) != int(spec["price_multiplier_bps"]):
            return False
        packet = value.get("packet")
        if not isinstance(packet, dict) or not verify_paid_home_packet(packet):
            return False
        if packet.get("packet_hash") != value.get("packet_hash") or packet.get("query_id") != value.get("query_id"):
            return False
        if packet.get("purchase_grant", {}).get("purchase_id") != value.get("purchase_id"):
            return False
        if str(packet.get("commerce", {}).get("payment_reference") or "").lower() != str(value.get("payment_reference") or "").lower():
            return False
        return True
    except Exception:
        return False


def enqueue(state_root: str | Path, entry: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    if not verify_queue_entry(entry, policy):
        raise QueueInvalid("QUEUE_ENTRY_INVALID")
    root = queue_root(state_root)
    entries = root / "entries"
    purchase_id = str(entry["purchase_id"])
    target = entries / f"{purchase_id}.json"
    existing = [p for p in entries.glob("*.json")] if entries.exists() else []
    if not target.exists() and len(existing) >= int(policy.get("max_queue_depth", 100)):
        raise QueueInvalid("QUEUE_DEPTH_LIMIT_REACHED")
    buyer = str(entry.get("buyer_actor_id") or "")
    if not target.exists() and buyer:
        same_buyer = 0
        for path in existing:
            row = _load(path)
            if row.get("buyer_actor_id") == buyer and not completion_path(state_root, str(row.get("purchase_id") or "")).exists():
                same_buyer += 1
        if same_buyer >= int(policy.get("max_queued_per_buyer", 3)):
            raise QueueInvalid("QUEUE_BUYER_PENDING_LIMIT_REACHED")
    status = _create_only(target, dict(entry))
    return {"queue_entry": status, "path": str(target), "purchase_id": purchase_id, "query_id": entry.get("query_id")}


def active_path(state_root: str | Path) -> Path:
    return queue_root(state_root) / "ACTIVE.json"


def dispatch_path(state_root: str | Path, purchase_id: str) -> Path:
    return queue_root(state_root) / "dispatches" / f"{purchase_id}.json"


def completion_path(state_root: str | Path, purchase_id: str) -> Path:
    return queue_root(state_root) / "completions" / f"{purchase_id}.json"


def _entries(state_root: str | Path, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    root = queue_root(state_root) / "entries"
    if not root.is_dir():
        return []
    rows = []
    for path in root.glob("*.json"):
        row = _load(path)
        if not verify_queue_entry(row, policy):
            raise QueueInvalid(f"QUEUE_STORED_ENTRY_INVALID:{path.name}")
        rows.append(row)
    return rows


def _sort_key(entry: Mapping[str, Any], policy: Mapping[str, Any], now: datetime) -> tuple[Any, ...]:
    return (
        -effective_level(entry, policy, now=now),
        int(entry.get("payment_block_number", 0)),
        int(entry.get("payment_log_index", 0)),
        str(entry.get("purchase_id") or ""),
    )


def _live_active(state_root: str | Path) -> dict[str, Any] | None:
    path = active_path(state_root)
    if not path.exists():
        return None
    active = _load(path)
    if active.get("schema") != ACTIVE_SCHEMA:
        raise QueueInvalid("QUEUE_ACTIVE_SCHEMA_INVALID")
    purchase_id = str(active.get("purchase_id") or "")
    if not purchase_id:
        raise QueueInvalid("QUEUE_ACTIVE_PURCHASE_MISSING")
    if completion_path(state_root, purchase_id).exists():
        return None
    return active


def claim_next(state_root: str | Path, policy: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    if int(policy.get("max_active_paid_search", 0)) != 1:
        raise QueueInvalid("QUEUE_CURRENT_IMPLEMENTATION_REQUIRES_SINGLE_ACTIVE_SLOT")
    path = active_path(state_root)
    active = _live_active(state_root)
    if active is not None:
        purchase_id = str(active["purchase_id"])
        entries = {str(x["purchase_id"]): x for x in _entries(state_root, policy)}
        entry = entries.get(purchase_id)
        if entry is None:
            raise QueueInvalid("QUEUE_ACTIVE_ENTRY_MISSING")
        return {"status": "ACTIVE_REPLAY", "entry": entry, "active": active}
    if path.exists():
        # The prior active request has a completion receipt. Clearing this pointer is
        # safe because completion is immutable and the shared workflow mutex serializes writers.
        path.unlink()
    candidates = [e for e in _entries(state_root, policy) if not completion_path(state_root, str(e["purchase_id"])).exists() and not dispatch_path(state_root, str(e["purchase_id"])).exists()]
    if not candidates:
        return {"status": "EMPTY", "entry": None, "active": None}
    candidates.sort(key=lambda e: _sort_key(e, policy, now))
    entry = candidates[0]
    body = {
        "schema": ACTIVE_SCHEMA,
        "status": "CLAIMED_NOT_PREEMPTIBLE",
        "purchase_id": entry["purchase_id"],
        "query_id": entry["query_id"],
        "packet_hash": entry["packet_hash"],
        "queue_level": entry["queue_level"],
        "effective_level_at_claim": effective_level(entry, policy, now=now),
        "claimed_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "preemptible": False,
    }
    active = {**body, "active_hash": digest(body)}
    _create_only(path, active)
    return {"status": "CLAIMED", "entry": entry, "active": active}


def mark_dispatched(state_root: str | Path, entry: Mapping[str, Any], *, outbox_commit: str, dispatched_at: datetime) -> dict[str, Any]:
    active = _live_active(state_root)
    if active is None or active.get("purchase_id") != entry.get("purchase_id") or active.get("packet_hash") != entry.get("packet_hash"):
        raise QueueInvalid("QUEUE_DISPATCH_REQUIRES_MATCHING_ACTIVE_LOCK")
    if len(str(outbox_commit)) != 40:
        raise QueueInvalid("QUEUE_DISPATCH_OUTBOX_COMMIT_REQUIRED")
    body = {
        "schema": DISPATCH_SCHEMA,
        "status": "DISPATCHED_TO_PERSISTENT_HOME",
        "purchase_id": entry["purchase_id"],
        "query_id": entry["query_id"],
        "packet_hash": entry["packet_hash"],
        "queue_level": entry["queue_level"],
        "outbox_commit": outbox_commit,
        "dispatched_at": dispatched_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "preempted_existing_execution": False,
    }
    receipt = {**body, "dispatch_hash": digest(body)}
    status = _create_only(dispatch_path(state_root, str(entry["purchase_id"])), receipt)
    return {"dispatch": status, "receipt": receipt}


def complete_active(state_root: str | Path, home_response: Mapping[str, Any], *, completed_at: datetime) -> dict[str, Any]:
    active = _live_active(state_root)
    if active is None:
        purchase_id = str(home_response.get("purchase_id") or "")
        path = completion_path(state_root, purchase_id)
        if path.exists():
            return {"completion": "IDEMPOTENT_REPLAY", "receipt": _load(path)}
        raise QueueInvalid("QUEUE_COMPLETION_WITHOUT_ACTIVE_REQUEST")
    purchase_id = str(home_response.get("purchase_id") or "")
    if purchase_id != active.get("purchase_id"):
        raise QueueInvalid("QUEUE_COMPLETION_PURCHASE_MISMATCH")
    receipt = home_response.get("buyer_query_receipt") or {}
    if home_response.get("mode") != "PAID_SETTLED" or receipt.get("status") not in {"DELIVERED", "REPLAYED"}:
        raise QueueInvalid("QUEUE_COMPLETION_REQUIRES_PAID_HOME_DELIVERY")
    if home_response.get("query_id") != active.get("query_id"):
        raise QueueInvalid("QUEUE_COMPLETION_QUERY_MISMATCH")
    body = {
        "schema": COMPLETION_SCHEMA,
        "status": "DELIVERED_ACTIVE_SLOT_RELEASED",
        "purchase_id": purchase_id,
        "query_id": home_response.get("query_id"),
        "execution_identity": receipt.get("execution_identity"),
        "response_hash": receipt.get("response_hash"),
        "home_response_hash": home_response.get("home_response_hash"),
        "completed_at": completed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "released_active_slot": True,
    }
    completion = {**body, "completion_hash": digest(body)}
    status = _create_only(completion_path(state_root, purchase_id), completion)
    path = active_path(state_root)
    if path.exists():
        current = _load(path)
        if current.get("purchase_id") != purchase_id:
            raise QueueConflict("QUEUE_ACTIVE_CHANGED_DURING_COMPLETION")
        path.unlink()
    return {"completion": status, "receipt": completion}


def snapshot(state_root: str | Path, policy: Mapping[str, Any], *, now: datetime, focus_purchase_id: str | None = None) -> dict[str, Any]:
    now = now.astimezone(timezone.utc)
    active = _live_active(state_root)
    rows = [e for e in _entries(state_root, policy) if not completion_path(state_root, str(e["purchase_id"])).exists()]
    active_id = str(active.get("purchase_id") or "") if active else None
    waiting = [e for e in rows if str(e["purchase_id"]) != active_id]
    waiting.sort(key=lambda e: _sort_key(e, policy, now))
    slot_min = int((policy.get("service_time_estimate_minutes") or {}).get("min", 5))
    slot_nominal = int((policy.get("service_time_estimate_minutes") or {}).get("nominal", 8))
    slot_max = int((policy.get("service_time_estimate_minutes") or {}).get("max", 15))
    if not (0 < slot_min <= slot_nominal <= slot_max):
        raise QueueInvalid("QUEUE_SERVICE_TIME_ESTIMATE_INVALID")
    public_rows = []
    for idx, entry in enumerate(waiting, start=1):
        active_ahead = 1 if active_id else 0
        ahead = active_ahead + idx - 1
        public_rows.append({
            "position": idx,
            "purchase_id": entry["purchase_id"],
            "query_id": entry["query_id"],
            "source_issue_number": entry.get("source_issue_number"),
            "queue_level": entry["queue_level"],
            "effective_level": effective_level(entry, policy, now=now),
            "queue_code": entry.get("queue_code"),
            "people_ahead_before_start": ahead,
            "estimated_wait_minutes": {
                "min": ahead * slot_min,
                "nominal": ahead * slot_nominal,
                "max": ahead * slot_max,
            },
        })
    focus = None
    if focus_purchase_id:
        if active_id == focus_purchase_id:
            focus = {
                "state": "ACTIVE",
                "position": 0,
                "people_ahead_before_start": 0,
                "estimated_wait_minutes": {"min": 0, "nominal": 0, "max": 0},
                "purchase_id": focus_purchase_id,
            }
        else:
            focus = next((dict(x, state="QUEUED") for x in public_rows if x["purchase_id"] == focus_purchase_id), None)
            if focus is None and completion_path(state_root, focus_purchase_id).exists():
                focus = {"state": "DELIVERED", "purchase_id": focus_purchase_id, "position": None, "people_ahead_before_start": 0, "estimated_wait_minutes": {"min": 0, "nominal": 0, "max": 0}}
    result = {
        "schema": SNAPSHOT_SCHEMA,
        "status": "ACTIVE" if active_id else ("QUEUED" if public_rows else "EMPTY"),
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "max_active_paid_search": 1,
        "preemption": False,
        "active": None if not active else {
            "purchase_id": active.get("purchase_id"),
            "query_id": active.get("query_id"),
            "queue_level": active.get("queue_level"),
            "effective_level_at_claim": active.get("effective_level_at_claim"),
            "claimed_at": active.get("claimed_at"),
        },
        "waiting_count": len(public_rows),
        "waiting": public_rows,
        "focus": focus,
        "eta_is_estimate_not_guarantee": True,
        "higher_tier_can_overtake_waiting_only": True,
        "active_request_can_be_preempted": False,
    }
    result["snapshot_hash"] = digest(result)
    return result


__all__ = [
    "QueueConflict",
    "QueueInvalid",
    "build_queue_entry",
    "claim_next",
    "complete_active",
    "effective_level",
    "enqueue",
    "level_spec",
    "mark_dispatched",
    "snapshot",
    "verify_queue_entry",
]
