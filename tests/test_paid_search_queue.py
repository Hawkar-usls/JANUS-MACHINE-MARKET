from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from runtime.commerce_authority import digest
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
)


def policy() -> dict:
    return json.loads((Path(__file__).resolve().parents[1] / "PAID_QUEUE_POLICY.json").read_text(encoding="utf-8"))


def packet_and_inputs(*, purchase_id: str, level: int, block_number: int, log_index: int, paid_at: datetime, buyer: str = "github:buyer"):
    tx_hash = "0x" + digest({"purchase_id": purchase_id})[:64]
    payment_ref = f"{tx_hash}:{log_index}"
    request = {
        "schema": "janus.machine_market.buyer_query_shadow_request.v1",
        "request_id": f"github-issue-id:{block_number}",
        "sku": "JANUS.SEARCH",
        "buyer_actor_id": buyer,
        "conversation_id": f"paid-{purchase_id}",
        "turn_index": 0,
        "message_text": "queue test",
        "created_at": paid_at.isoformat().replace("+00:00", "Z"),
        "max_turns": 1,
        "max_message_utf8_bytes": 4000,
        "max_answer_utf8_bytes": 6000,
        "conversation_history_turns": 0,
        "source_issue_number": block_number,
        "source_issue_id": block_number,
        "request_origin": "FOREIGN_PAID_SEARCH",
        "queue_level": level,
    }
    quote = {
        "schema": "janus.machine_market.quote.v1",
        "sku": "JANUS.SEARCH",
        "request_hash": digest(request),
        "amount_usdt_micros": 50_000 * {1: 1, 2: 1.5, 3: 2.25, 4: 3.5, 5: 5}[level],
        "asset": "USDT",
        "chain_id": 1,
        "token_contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "receiving_address": "0x7149081aea54fbef57effeb52a5a966b81cc03a0",
        "expires_at": (paid_at + timedelta(minutes=15)).isoformat(),
        "nonce": f"n-{purchase_id}",
        "policy_version": "test",
    }
    quote["amount_usdt_micros"] = int(quote["amount_usdt_micros"])
    quote["quote_hash"] = digest({k: v for k, v in quote.items() if k != "quote_hash"})
    receipt = {
        "schema": "janus.machine_market.payment_receipt.v1",
        "status": "CONFIRMED",
        "quote_hash": quote["quote_hash"],
        "chain_id": 1,
        "token_contract": quote["token_contract"],
        "to": quote["receiving_address"],
        "amount_usdt_micros": quote["amount_usdt_micros"],
        "required_confirmations": 12,
        "confirmations": 12,
        "tx_hash": tx_hash,
        "log_index": log_index,
        "payment_reference": payment_ref,
        "block_number": block_number,
        "block_hash": "0x" + digest({"block": block_number})[:64],
        "block_timestamp": paid_at.isoformat().replace("+00:00", "Z"),
    }
    entitlement = {
        "enabled": True,
        "buyer_actor_id": buyer,
        "max_turns": 1,
        "max_message_utf8_bytes": 4000,
        "max_answer_utf8_bytes": 6000,
        "conversation_history_turns": 0,
        "entitlement_nonce": f"ent-{purchase_id}",
        "read_only_conversation": True,
        "external_effect_authorized": False,
    }
    grant = {
        "schema": "janus.machine_market.purchase_grant.v1",
        "purchase_id": purchase_id,
        "sku": "JANUS.SEARCH",
        "offer_hash": None,
        "quote_hash": quote["quote_hash"],
        "request_hash": digest(request),
        "terms_hash": None,
        "payment_reference": payment_ref,
        "amount_usdt_micros": quote["amount_usdt_micros"],
        "policy_version": "test",
        "status": "PURCHASE_SETTLED",
        "execution_authority_granted": False,
        "allowed_operation": "REQUEST_BOUNDED_BUYER_QUERY",
        "next_gate": "JANUS_HOME_READ_ONLY_BUYER_QUERY",
        "authority_ceiling": {"sku": "JANUS.SEARCH", "production_activator_authority": False, "external_effect_authority": False},
        "buyer_query_entitlement": entitlement,
        "expires_at": None,
        "reasons": ["PAYMENT_CONFIRMED_PURCHASE_GRANT_IS_NOT_EXECUTION_AUTHORITY"],
    }
    grant["grant_hash"] = digest(grant)
    message_hash = __import__("hashlib").sha256(request["message_text"].encode()).hexdigest()
    query = {
        "schema": "janus.machine_market.buyer_query.v1",
        "purchase_id": purchase_id,
        "purchase_grant_hash": grant["grant_hash"],
        "sku": "JANUS.SEARCH",
        "buyer_actor_id": buyer,
        "conversation_id": request["conversation_id"],
        "turn_index": 0,
        "entitlement_nonce": entitlement["entitlement_nonce"],
        "message_text": request["message_text"],
        "message_hash": message_hash,
        "query_id": "bq-" + digest({"purchase_id": purchase_id, "conversation_id": request["conversation_id"], "turn_index": 0, "message_hash": message_hash, "entitlement_nonce": entitlement["entitlement_nonce"]}),
        "conversation_history": [],
        "requested_output": {"mode": "JANUS_READ_ONLY_CONVERSATION"},
        "created_at": request["created_at"],
    }
    query["query_hash"] = digest(query)
    packet = {
        "schema": "janus.machine_market.home_buyer_query_packet.v1",
        "market_repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
        "home_repository": "Hawkar-usls/Hawkar-usls",
        "transport_mode": "PHYSARIUS_CREDENTIALLESS_PULL",
        "mode": "PAID_SETTLED",
        "request_origin": "FOREIGN_PAID_SEARCH",
        "request_id": request["request_id"],
        "request_hash": digest(request),
        "queue_level": level,
        "offer": {"schema": "janus.machine_market.paid_search_offer.v1", "sku": "JANUS.SEARCH", "quote_hash": quote["quote_hash"], "price": {"amount_usdt_micros": quote["amount_usdt_micros"], "asset": "USDT", "chain_id": 1}, "payment_required": True, "production_purchase": True, "buyer_query_turns": 1},
        "purchase_grant": grant,
        "purchase_grant_hash": grant["grant_hash"],
        "buyer_query": query,
        "query_id": query["query_id"],
        "query_hash": query["query_hash"],
        "return_route": {"repository": "Hawkar-usls/JANUS-MACHINE-MARKET", "source_issue_number": block_number, "source_issue_id": block_number},
        "commerce": {"quote": quote, "quote_hash": quote["quote_hash"], "payment_receipt": receipt, "payment_reference": payment_ref, "settlement_verified": True},
        "money_enabled": True,
        "payment_required": True,
        "production_purchase": True,
        "execution_authority_granted": False,
        "command_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "scientific_evidence_authority_granted": False,
        "world_truth_authority_granted": False,
        "laws": ["PAYMENT != COMMAND", "PURCHASE_GRANT != EXECUTION_AUTHORITY"],
    }
    packet["offer_hash"] = digest(packet["offer"])
    packet["packet_hash"] = digest(packet)
    return request, grant, packet, receipt


def entry(*, purchase_id="jp-a", level=1, block=100, log=1, paid_at=None, buyer="github:buyer"):
    paid_at = paid_at or datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
    req, grant, packet, receipt = packet_and_inputs(purchase_id=purchase_id, level=level, block_number=block, log_index=log, paid_at=paid_at, buyer=buyer)
    return build_queue_entry(request=req, purchase_grant=grant, packet=packet, payment_receipt=receipt, policy=policy())


def test_higher_level_overtakes_waiting_but_not_active(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    enqueue(tmp_path, entry(purchase_id="jp-l1", level=1, block=100), p)
    first = claim_next(tmp_path, p, now=now)
    assert first["entry"]["purchase_id"] == "jp-l1"
    enqueue(tmp_path, entry(purchase_id="jp-l5", level=5, block=101), p)
    replay = claim_next(tmp_path, p, now=now + timedelta(minutes=1))
    assert replay["status"] == "ACTIVE_REPLAY"
    assert replay["entry"]["purchase_id"] == "jp-l1"


def test_priority_then_chain_order_is_deterministic(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 5, tzinfo=timezone.utc)
    enqueue(tmp_path, entry(purchase_id="jp-b", level=3, block=101, log=0), p)
    enqueue(tmp_path, entry(purchase_id="jp-a", level=3, block=100, log=9), p)
    enqueue(tmp_path, entry(purchase_id="jp-c", level=5, block=999, log=0), p)
    picked = claim_next(tmp_path, p, now=now)
    assert picked["entry"]["purchase_id"] == "jp-c"


def test_aging_prevents_permanent_low_tier_starvation():
    p = policy(); paid = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
    low = entry(level=1, paid_at=paid)
    assert effective_level(low, p, now=paid + timedelta(minutes=29)) == 1
    assert effective_level(low, p, now=paid + timedelta(minutes=30)) == 2
    assert effective_level(low, p, now=paid + timedelta(minutes=120)) == 5


def test_exact_enqueue_is_idempotent_and_conflict_fails(tmp_path: Path):
    p = policy(); e = entry()
    assert enqueue(tmp_path, e, p)["queue_entry"] == "CREATED"
    assert enqueue(tmp_path, e, p)["queue_entry"] == "IDEMPOTENT_REPLAY"
    bad = dict(e); bad["queue_level"] = 2
    with pytest.raises(QueueInvalid):
        enqueue(tmp_path, bad, p)


def test_snapshot_exposes_position_and_wait_range(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    enqueue(tmp_path, entry(purchase_id="jp-1", level=1, block=100), p)
    enqueue(tmp_path, entry(purchase_id="jp-2", level=2, block=101), p)
    s = snapshot(tmp_path, p, now=now, focus_purchase_id="jp-1")
    assert s["focus"]["state"] == "QUEUED"
    assert s["focus"]["people_ahead_before_start"] == 1
    assert s["focus"]["estimated_wait_minutes"] == {"min": 5, "nominal": 8, "max": 15}
    assert s["eta_is_estimate_not_guarantee"] is True


def test_completion_releases_only_matching_active_slot(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    e = entry(purchase_id="jp-one", level=4, block=100)
    enqueue(tmp_path, e, p)
    claimed = claim_next(tmp_path, p, now=now)
    mark_dispatched(tmp_path, claimed["entry"], outbox_commit="a" * 40, dispatched_at=now)
    home = {
        "mode": "PAID_SETTLED",
        "purchase_id": "jp-one",
        "query_id": e["query_id"],
        "home_response_hash": "b" * 64,
        "buyer_query_receipt": {"status": "DELIVERED", "execution_identity": "tr-one", "response_hash": "c" * 64},
    }
    done = complete_active(tmp_path, home, completed_at=now + timedelta(minutes=3))
    assert done["completion"] == "CREATED"
    assert claim_next(tmp_path, p, now=now + timedelta(minutes=4))["status"] == "EMPTY"


def test_wrong_purchase_cannot_release_active_slot(tmp_path: Path):
    p = policy(); now = datetime(2026, 9, 4, 0, 10, tzinfo=timezone.utc)
    enqueue(tmp_path, entry(purchase_id="jp-one", level=4, block=100), p)
    claim_next(tmp_path, p, now=now)
    bad = {"mode": "PAID_SETTLED", "purchase_id": "jp-other", "query_id": "x", "buyer_query_receipt": {"status": "DELIVERED"}}
    with pytest.raises(QueueInvalid, match="QUEUE_COMPLETION_PURCHASE_MISMATCH"):
        complete_active(tmp_path, bad, completed_at=now)
