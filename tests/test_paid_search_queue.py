from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from runtime.commerce_authority import digest
from runtime.paid_search_checkout import issue_invoice, settle_invoice
from runtime.paid_search_queue import (
    QueueConflict,
    QueueInvalid,
    build_queue_entry,
    claim_next,
    complete_active,
    effective_level,
    enqueue,
    mark_dispatched,
    snapshot,
    verify_queue_entry,
)

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = "0x7149081aea54fbef57effeb52a5a966b81cc03a0"


def policy() -> dict:
    return json.loads((ROOT / "PAID_QUEUE_POLICY.json").read_text(encoding="utf-8"))


def pricing() -> dict:
    return json.loads((ROOT / "PRICING.json").read_text(encoding="utf-8"))


def request(*, purchase_seed: str, level: int, paid_at: datetime, buyer: str = "github:buyer") -> dict:
    issue_id = 1_000_000 + int(digest({"seed": purchase_seed})[:8], 16)
    return {
        "schema": "janus.machine_market.buyer_query_shadow_request.v1",
        "request_id": f"github-issue-id:{issue_id}",
        "sku": "JANUS.SEARCH",
        "buyer_actor_id": buyer,
        "conversation_id": f"paid-{purchase_seed}",
        "turn_index": 0,
        "message_text": "queue test",
        "created_at": paid_at.isoformat().replace("+00:00", "Z"),
        "max_turns": 1,
        "max_message_utf8_bytes": 4000,
        "max_answer_utf8_bytes": 6000,
        "conversation_history_turns": 0,
        "source_issue_number": issue_id,
        "source_issue_id": issue_id,
        "request_origin": "FOREIGN_PAID_SEARCH",
        "queue_level": level,
    }


def bundle(*, seed: str = "a", level: int = 1, block: int = 100, log: int = 1, paid_at: datetime | None = None, buyer: str = "github:buyer"):
    paid_at = paid_at or datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
    req = request(purchase_seed=seed, level=level, paid_at=paid_at, buyer=buyer)
    inv = issue_invoice(request=req, pricing=pricing(), issued_at=paid_at - timedelta(minutes=1), receiving_address=RECEIVER)
    tx_hash = "0x" + digest({"seed": seed, "block": block, "log": log})[:64]
    receipt = {
        "schema": "janus.machine_market.payment_receipt.v1",
        "status": "CONFIRMED",
        "quote_hash": inv["quote_hash"],
        "chain_id": 1,
        "token_contract": inv["quote"]["token_contract"],
        "to": inv["quote"]["receiving_address"],
        "amount_usdt_micros": inv["amount_usdt_micros"],
        "required_confirmations": 12,
        "confirmations": 12,
        "tx_hash": tx_hash,
        "log_index": log,
        "payment_reference": f"{tx_hash}:{log}",
        "block_number": block,
        "block_hash": "0x" + digest({"block": block})[:64],
        "block_timestamp": paid_at.isoformat().replace("+00:00", "Z"),
    }
    grant, packet = settle_invoice(
        invoice=inv,
        request=req,
        payment_receipt=receipt,
        readiness={"money_enabled": True, "autonomous_purchase_declared": True},
        witness={"foreign_agent_witness": True},
        product={"sku": "JANUS.SEARCH", "machine_purchase": True},
    )
    entry = build_queue_entry(
        request=req,
        purchase_grant=grant,
        packet=packet,
        payment_receipt=receipt,
        policy=policy(),
    )
    assert verify_queue_entry(entry, policy())
    return req, inv, receipt, grant, packet, entry


def home_response(entry: dict) -> dict:
    return {
        "mode": "PAID_SETTLED",
        "purchase_id": entry["purchase_id"],
        "query_id": entry["query_id"],
        "home_response_hash": "b" * 64,
        "buyer_query_receipt": {
            "status": "DELIVERED",
            "execution_identity": "tr-" + entry["purchase_id"],
            "response_hash": "c" * 64,
        },
    }


def test_invoice_and_packet_freeze_queue_level_and_price():
    _, inv1, _, _, packet1, _ = bundle(seed="l1", level=1)
    _, inv5, _, _, packet5, _ = bundle(seed="l5", level=5, block=101)
    assert inv1["amount_usdt_micros"] == 50_000
    assert inv5["amount_usdt_micros"] == 250_000
    assert inv1["queue_level"] == packet1["queue_level"] == 1
    assert inv5["queue_level"] == packet5["queue_level"] == 5
    assert packet1["queue_contract_version"] == "paid-search-queue-v1"
    assert packet5["queue_contract_version"] == "paid-search-queue-v1"


def test_higher_level_overtakes_waiting_but_never_active(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    low = bundle(seed="low", level=1, block=100)[-1]
    high = bundle(seed="high", level=5, block=101)[-1]
    enqueue(tmp_path, low, p)
    first = claim_next(tmp_path, p, now=now)
    assert first["entry"]["purchase_id"] == low["purchase_id"]
    enqueue(tmp_path, high, p)
    replay = claim_next(tmp_path, p, now=now + timedelta(minutes=1))
    assert replay["status"] == "ACTIVE_REPLAY"
    assert replay["entry"]["purchase_id"] == low["purchase_id"]


def test_priority_then_chain_order_is_deterministic(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 5, tzinfo=timezone.utc)
    e1 = bundle(seed="b", level=3, block=101, log=0)[-1]
    e2 = bundle(seed="a", level=3, block=100, log=9)[-1]
    e3 = bundle(seed="c", level=5, block=999, log=0)[-1]
    for e in (e1, e2, e3): enqueue(tmp_path, e, p)
    picked = claim_next(tmp_path, p, now=now)
    assert picked["entry"]["purchase_id"] == e3["purchase_id"]


def test_equal_priority_uses_payment_block_then_log_index(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 5, tzinfo=timezone.utc)
    later_block = bundle(seed="later", level=3, block=101, log=0)[-1]
    earlier_block = bundle(seed="earlier", level=3, block=100, log=9)[-1]
    enqueue(tmp_path, later_block, p); enqueue(tmp_path, earlier_block, p)
    picked = claim_next(tmp_path, p, now=now)
    assert picked["entry"]["purchase_id"] == earlier_block["purchase_id"]


def test_aging_prevents_permanent_low_tier_starvation():
    p = policy(); paid = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
    low = bundle(seed="aging", level=1, block=100, paid_at=paid)[-1]
    assert effective_level(low, p, now=paid + timedelta(minutes=29)) == 1
    assert effective_level(low, p, now=paid + timedelta(minutes=30)) == 2
    assert effective_level(low, p, now=paid + timedelta(minutes=120)) == 5


def test_exact_enqueue_is_idempotent_and_tamper_fails(tmp_path: Path):
    p = policy(); e = bundle(seed="idem", level=1, block=100)[-1]
    assert enqueue(tmp_path, e, p)["queue_entry"] == "CREATED"
    assert enqueue(tmp_path, e, p)["queue_entry"] == "IDEMPOTENT_REPLAY"
    bad = deepcopy(e); bad["queue_level"] = 2
    with pytest.raises(QueueInvalid): enqueue(tmp_path, bad, p)


def test_per_buyer_pending_limit_and_global_depth_fail_closed(tmp_path: Path):
    p = policy()
    for idx in range(3):
        enqueue(tmp_path, bundle(seed=f"buyer-{idx}", level=1, block=100+idx, buyer="github:same")[-1], p)
    with pytest.raises(QueueInvalid, match="BUYER_PENDING_LIMIT"):
        enqueue(tmp_path, bundle(seed="buyer-4", level=1, block=104, buyer="github:same")[-1], p)

    tiny = deepcopy(p); tiny["max_queue_depth"] = 3; tiny["max_queued_per_buyer"] = 100
    other_root = tmp_path / "depth"
    for idx in range(3):
        enqueue(other_root, bundle(seed=f"depth-{idx}", level=1, block=200+idx, buyer=f"github:{idx}")[-1], tiny)
    with pytest.raises(QueueInvalid, match="DEPTH_LIMIT"):
        enqueue(other_root, bundle(seed="depth-4", level=1, block=204, buyer="github:4")[-1], tiny)


def test_completed_history_does_not_consume_pending_capacity(tmp_path: Path):
    p = deepcopy(policy())
    p["max_queue_depth"] = 1
    p["max_queued_per_buyer"] = 10
    now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    first = bundle(seed="history-first", level=1, block=300, buyer="github:first")[-1]
    enqueue(tmp_path, first, p)
    claimed = claim_next(tmp_path, p, now=now)
    mark_dispatched(tmp_path, claimed["entry"], outbox_commit="a" * 40, dispatched_at=now)
    complete_active(tmp_path, home_response(first), completed_at=now + timedelta(minutes=1))
    historical = tmp_path / "state/commerce/paid-search-queue/entries" / f"{first['purchase_id']}.json"
    assert historical.exists(), "immutable queue history must remain preserved"
    second = bundle(seed="history-second", level=1, block=301, buyer="github:second")[-1]
    assert enqueue(tmp_path, second, p)["queue_entry"] == "CREATED"


def test_snapshot_exposes_position_and_estimate_not_guarantee(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    low = bundle(seed="snap-low", level=1, block=100)[-1]
    high = bundle(seed="snap-high", level=2, block=101)[-1]
    enqueue(tmp_path, low, p); enqueue(tmp_path, high, p)
    s = snapshot(tmp_path, p, now=now, focus_purchase_id=low["purchase_id"])
    assert s["focus"]["state"] == "QUEUED"
    assert s["focus"]["people_ahead_before_start"] == 1
    assert s["focus"]["estimated_wait_minutes"] == {"min": 5, "nominal": 8, "max": 15}
    assert s["eta_is_estimate_not_guarantee"] is True
    assert s["active_request_can_be_preempted"] is False


def test_completion_releases_only_matching_active_slot_and_retry_is_idempotent(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    e = bundle(seed="complete", level=4, block=100)[-1]
    enqueue(tmp_path, e, p)
    claimed = claim_next(tmp_path, p, now=now)
    mark_dispatched(tmp_path, claimed["entry"], outbox_commit="a" * 40, dispatched_at=now)
    home = home_response(e)
    done = complete_active(tmp_path, home, completed_at=now + timedelta(minutes=3))
    assert done["completion"] == "CREATED"
    replay = complete_active(tmp_path, home, completed_at=now + timedelta(minutes=4))
    assert replay["completion"] == "IDEMPOTENT_REPLAY"
    assert claim_next(tmp_path, p, now=now + timedelta(minutes=5))["status"] == "EMPTY"


def test_wrong_purchase_cannot_release_active_slot(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    e = bundle(seed="active", level=4, block=100)[-1]
    enqueue(tmp_path, e, p); claim_next(tmp_path, p, now=now)
    bad = home_response(e); bad["purchase_id"] = "jp-other"
    with pytest.raises(QueueInvalid, match="QUEUE_COMPLETION_PURCHASE_MISMATCH"):
        complete_active(tmp_path, bad, completed_at=now)


def test_second_conflicting_dispatch_receipt_fails_closed(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    e = bundle(seed="dispatch", level=2, block=100)[-1]
    enqueue(tmp_path, e, p); claim_next(tmp_path, p, now=now)
    assert mark_dispatched(tmp_path, e, outbox_commit="a"*40, dispatched_at=now)["dispatch"] == "CREATED"
    assert mark_dispatched(tmp_path, e, outbox_commit="a"*40, dispatched_at=now)["dispatch"] == "IDEMPOTENT_REPLAY"
    with pytest.raises(QueueConflict):
        mark_dispatched(tmp_path, e, outbox_commit="b"*40, dispatched_at=now)
