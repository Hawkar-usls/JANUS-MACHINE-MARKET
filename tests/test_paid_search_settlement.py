from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from runtime.commerce_authority import MIN_CONFIRMATIONS
from runtime.paid_search_checkout import issue_invoice
from runtime.paid_search_settlement import canonical_confirmed_receipt, consensus_payment_observation

TX = "0x" + "ab" * 32
BLOCK = "0x" + "cd" * 32


def pricing():
    return {
        "currency": "USDT",
        "chain_id": 1,
        "quote_ttl_seconds": 900,
        "products": {
            "JANUS.SEARCH": {
                "base_unit_usdt_micros": 50_000,
                "modes": {"FAST": {"multiplier_bps": 10_000}},
            }
        },
    }


def request():
    return {
        "schema": "janus.machine_market.buyer_query_shadow_request.v1",
        "request_id": "github-issue-id:9991",
        "sku": "JANUS.SEARCH",
        "buyer_actor_id": "github:external-buyer",
        "conversation_id": "paid-market-issue-9991",
        "turn_index": 0,
        "message_text": "quorum test",
        "created_at": "2026-09-04T12:00:00Z",
        "max_turns": 1,
        "max_message_utf8_bytes": 4000,
        "max_answer_utf8_bytes": 6000,
        "conversation_history_turns": 0,
        "source_issue_number": 9991,
        "source_issue_id": 9991001,
        "request_origin": "FOREIGN_PAID_SEARCH",
    }


def quote():
    return issue_invoice(
        request=request(),
        pricing=pricing(),
        issued_at=datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
    )["quote"]


def observation(confirmations=12, *, block_hash=BLOCK, status=None):
    q = quote()
    return {
        "schema": "janus.machine_market.payment_receipt.v1",
        "status": status or ("CONFIRMED" if confirmations >= MIN_CONFIRMATIONS else "OBSERVED"),
        "quote_hash": q["quote_hash"],
        "chain_id": 1,
        "token_contract": q["token_contract"],
        "to": q["receiving_address"],
        "amount_usdt_micros": q["amount_usdt_micros"],
        "required_confirmations": MIN_CONFIRMATIONS,
        "tx_hash": TX,
        "log_index": 7,
        "payment_reference": f"{TX}:7",
        "block_number": 24_000_000,
        "block_hash": block_hash,
        "block_timestamp": "2026-09-04T12:10:00Z",
        "confirmations": confirmations,
    }


def test_two_matching_confirmed_rpc_observations_form_quorum():
    q = quote()
    out, meta = consensus_payment_observation(q, [("rpc-a", observation(12)), ("rpc-b", observation(14))])
    assert out["status"] == "CONFIRMED"
    assert out["confirmations"] == 12
    assert meta["status"] == "CONFIRMED"
    assert meta["agreeing_payment_observers"] == 2
    assert meta["min_confirmations_observed"] == 12


def test_confirmation_quorum_uses_conservative_minimum():
    q = quote()
    out, meta = consensus_payment_observation(q, [("rpc-a", observation(11)), ("rpc-b", observation(15))])
    assert out["status"] == "OBSERVED"
    assert out["confirmations"] == 11
    assert meta["status"] == "OBSERVED"


def test_conflicting_canonical_block_hash_quarantines():
    q = quote()
    other = "0x" + "ef" * 32
    out, meta = consensus_payment_observation(q, [("rpc-a", observation(12)), ("rpc-b", observation(12, block_hash=other))])
    assert out["status"] == "QUARANTINED"
    assert out["reason"] == "RPC_OBSERVATION_CONFLICT"
    assert meta["status"] == "CONFLICT"


def test_only_one_payment_observer_never_settles():
    q = quote()
    not_found = {
        "schema": "janus.machine_market.payment_receipt.v1",
        "status": "NOT_FOUND",
        "quote_hash": q["quote_hash"],
        "chain_id": 1,
        "token_contract": q["token_contract"],
        "to": q["receiving_address"],
        "amount_usdt_micros": q["amount_usdt_micros"],
        "required_confirmations": MIN_CONFIRMATIONS,
        "confirmations": 0,
    }
    out, meta = consensus_payment_observation(q, [("rpc-a", observation(20)), ("rpc-b", not_found)])
    assert out["status"] == "QUARANTINED"
    assert out["reason"] == "RPC_PAYMENT_QUORUM_UNAVAILABLE"
    assert meta["status"] == "PAYMENT_QUORUM_UNAVAILABLE"


def test_canonical_confirmed_receipt_is_stable_as_live_confirmations_grow():
    at_12 = canonical_confirmed_receipt(observation(12))
    at_300 = canonical_confirmed_receipt(observation(300))
    assert at_12 == at_300
    assert at_12["confirmations"] == MIN_CONFIRMATIONS == 12
    assert at_12["payment_reference"] == f"{TX}:7"
    assert at_12["block_hash"] == BLOCK


def test_provider_quarantine_is_not_majority_overridden():
    q = quote()
    quarantined = deepcopy(observation(12))
    quarantined["status"] = "QUARANTINED"
    quarantined["reason"] = "BLOCK_HASH_NOT_CANONICAL"
    quarantined["confirmations"] = 0
    out, meta = consensus_payment_observation(
        q,
        [("rpc-a", observation(12)), ("rpc-b", observation(12)), ("rpc-c", quarantined)],
    )
    assert out["status"] == "QUARANTINED"
    assert out["reason"] == "RPC_PROVIDER_QUARANTINE"
    assert meta["status"] == "PROVIDER_QUARANTINE"
