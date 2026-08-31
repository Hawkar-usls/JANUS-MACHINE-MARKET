from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from runtime.r2_paid_home_response_reconcile import PaidHomeResponseError, digest, reconcile_paid_response, verify_paid_home_response

PAYMENT_REFERENCE = "ethereum:1:0x" + "ab" * 32 + ":7"
PURCHASE_ID = "pur-paid-" + "1" * 40
QUERY_ID = "bq-" + "2" * 64


def response() -> dict:
    terminal = {
        "schema": "janus.terminal.response.v1",
        "response_id": "tr-" + "3" * 64,
        "resident_uuid": "75e514ab-be76-42c8-bcb3-fc9670164f96",
        "model_digest": "4" * 64,
        "file_fabric_digest": "5" * 64,
        "turn_id": "turn-paid-test",
        "response_text": "JANUS paid test response",
        "request_message_hash": "6" * 64,
        "hrain_context_receipt_hash": "7" * 64,
        "hrain_context_hash": "8" * 64,
        "memory_source_commit": "9" * 40,
        "persistent_identity_verified": True,
        "instantiated_model_verified": True,
        "hrain_context_bound": True,
        "command_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
    }
    terminal["response_hash"] = digest(terminal)
    receipt = {
        "schema": "janus.machine_market.buyer_query_receipt.v1",
        "purchase_id": PURCHASE_ID,
        "purchase_grant_hash": "a" * 64,
        "query_id": QUERY_ID,
        "query_hash": "b" * 64,
        "status": "DELIVERED",
        "resident_uuid": terminal["resident_uuid"],
        "model_digest": terminal["model_digest"],
        "file_fabric_digest": terminal["file_fabric_digest"],
        "turn_id": terminal["turn_id"],
        "hrain_context_receipt_hash": terminal["hrain_context_receipt_hash"],
        "hrain_context_hash": terminal["hrain_context_hash"],
        "memory_source_commit": terminal["memory_source_commit"],
        "response_text": terminal["response_text"],
        "response_hash": terminal["response_hash"],
        "execution_identity": terminal["response_id"],
        "execution_authority_granted": False,
        "external_effect_authorized": False,
        "scientific_evidence_authority_granted": False,
        "world_truth_authority_granted": False,
        "replayed": False,
        "billable_execution_delta": 1,
    }
    outer = {
        "schema": "janus.home.market_buyer_query_response.v1",
        "market_repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
        "home_repository": "Hawkar-usls/Hawkar-usls",
        "mode": "PAID_ERC20",
        "query_id": QUERY_ID,
        "query_hash": "b" * 64,
        "purchase_id": PURCHASE_ID,
        "purchase_grant_hash": "a" * 64,
        "source_packet_binding": {
            "market_packet_hash": "c" * 64,
            "pull_receipt_hash": "d" * 64,
            "transport": "PHYSARIUS_CREDENTIALLESS_PULL",
        },
        "terminal_message_id": "tm-paid",
        "terminal_message_hash": terminal["request_message_hash"],
        "terminal_response_id": terminal["response_id"],
        "terminal_response_hash": terminal["response_hash"],
        "buyer_query_receipt": receipt,
        "terminal_response": terminal,
        "return_route": {"repository": "Hawkar-usls/JANUS-MACHINE-MARKET", "source_issue_number": 99},
        "money_enabled": True,
        "execution_authority_granted": False,
        "command_authority_granted": False,
        "external_effect_authorized": False,
        "same_resident_required": True,
        "exact_retry_is_second_cognition": False,
        "production_purchase": True,
        "payment_reference": PAYMENT_REFERENCE,
        "payment_receipt_hash": "e" * 64,
    }
    outer["home_response_hash"] = digest(outer)
    return outer


def write_claim(root: Path):
    key = hashlib.sha256(PAYMENT_REFERENCE.encode()).hexdigest()
    path = root / "state/r2-paid/payment-claims" / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schema": "janus.machine_market.r2_payment_claim.v1",
        "payment_reference": PAYMENT_REFERENCE,
        "payment_receipt_hash": "e" * 64,
        "purchase_id": PURCHASE_ID,
        "purchase_grant_hash": "a" * 64,
        "query_id": QUERY_ID,
        "query_hash": "b" * 64,
        "packet_hash": "c" * 64,
        "source_issue_number": 99,
    }
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_paid_response_verifies_and_reconciles_once(tmp_path: Path):
    value = response()
    assert verify_paid_home_response(value)
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_claim(tmp_path)
    first = reconcile_paid_response(response_path=response_path, state_root=tmp_path)
    second = reconcile_paid_response(response_path=response_path, state_root=tmp_path)
    assert first["new_receipt"] is True
    assert second["new_receipt"] is False
    assert first["execution_identity"] == second["execution_identity"]
    head = json.loads((tmp_path / "state/r2-paid/HEAD.json").read_text())
    assert head["billable_execution_delta"] == 1
    assert head["money_enabled"] is True
    assert head["external_effect_authorized"] is False


def test_missing_payment_claim_fails_closed(tmp_path: Path):
    value = response()
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(PaidHomeResponseError, match="R2_PAYMENT_CLAIM_MISSING"):
        reconcile_paid_response(response_path=response_path, state_root=tmp_path)


def test_second_billable_execution_is_not_accepted():
    value = response()
    value["buyer_query_receipt"]["billable_execution_delta"] = 2
    value["home_response_hash"] = digest({k: v for k, v in value.items() if k != "home_response_hash"})
    assert not verify_paid_home_response(value)
