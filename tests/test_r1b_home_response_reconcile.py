from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.r1b_home_response_reconcile import (
    HomeResponseError,
    digest,
    reconcile_response,
    verify_home_response,
)


def home_response() -> dict:
    terminal = {
        "schema": "janus.terminal.response.v1",
        "response_id": "tr-test",
        "created_at": 1.0,
        "terminal_repository": "Hawkar-usls/-Terminal-for-Janus",
        "conversation_id": "market::conv-1",
        "request_message_id": "tm-test",
        "request_message_hash": "a" * 64,
        "resident_id": "JANUS",
        "resident_uuid": "75e514ab-be76-42c8-bcb3-fc9670164f96",
        "model_digest": "b" * 64,
        "file_fabric_digest": "c" * 64,
        "turn_id": "turn-test",
        "response_mode": "MODEL_BOUND_HRAIN_MEMORY_CONVERSATION_PROOF",
        "response_text": "JANUS ONLINE test response",
        "hrain_context_bound": True,
        "hrain_context_receipt_hash": "d" * 64,
        "hrain_context_hash": "e" * 64,
        "hrain_locked_head_sha": "f" * 40,
        "memory_source_commit": "1" * 40,
        "memory_selected_count": 0,
        "memory_selected_paths": [],
        "memory_match_status": "NO_RELEVANT_MEMORY_SELECTED",
        "empty_memory_is_hrain_failure": False,
        "empty_memory_is_negative_evidence": False,
        "memory_path": "META_REGISTRY_DB -> HRAIN -> JANUS -> TERMINAL",
        "memory_retrieval_executed_by": "Hawkar-usls/Hrain",
        "meta_registry_access_performed_by_home": False,
        "memory_content_is_command": False,
        "memory_context_is_evidence": False,
        "memory_grants_authority": False,
        "instantiated_model_verified": True,
        "persistent_identity_verified": True,
        "terminal_interface_bound": True,
        "command_authority_granted": False,
        "human_authorized_write": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "world_truth_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "terminal": "JANUS_TERMINAL_CONVERSATION_RESPONSE_READY",
        "laws": ["TERMINAL_MESSAGE != COMMAND"],
    }
    terminal["response_hash"] = digest(terminal)
    receipt = {
        "schema": "janus.machine_market.buyer_query_receipt.v1",
        "purchase_id": "pur-test",
        "purchase_grant_hash": "2" * 64,
        "query_id": "bq-" + "3" * 64,
        "query_hash": "4" * 64,
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
        "billable_execution_delta": 0,
    }
    response = {
        "schema": "janus.home.market_buyer_query_response.v1",
        "market_repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
        "home_repository": "Hawkar-usls/Hawkar-usls",
        "mode": "ZERO_PRICE_SHADOW",
        "query_id": receipt["query_id"],
        "query_hash": receipt["query_hash"],
        "purchase_id": receipt["purchase_id"],
        "purchase_grant_hash": receipt["purchase_grant_hash"],
        "source_packet_binding": {
            "market_source_commit": "5" * 40,
            "market_packet_path": ".janus/market-home-outbox/test.packet.json",
            "market_packet_git_blob_sha": "6" * 40,
            "market_packet_file_sha256": "7" * 64,
            "market_packet_hash": "8" * 64,
            "pull_receipt_hash": "9" * 64,
            "transport": "PHYSARIUS_CREDENTIALLESS_PULL",
        },
        "terminal_message_id": terminal["request_message_id"],
        "terminal_message_hash": terminal["request_message_hash"],
        "terminal_response_id": terminal["response_id"],
        "terminal_response_hash": terminal["response_hash"],
        "buyer_query_receipt": receipt,
        "terminal_response": terminal,
        "return_route": {
            "repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
            "source_issue_number": 42,
            "source_issue_id": 4242,
        },
        "money_enabled": False,
        "execution_authority_granted": False,
        "command_authority_granted": False,
        "external_effect_authorized": False,
        "same_resident_required": True,
        "exact_retry_is_second_cognition": False,
    }
    response["home_response_hash"] = digest(response)
    return response


def test_valid_home_response_verifies():
    assert verify_home_response(home_response())


def test_tampered_response_fails():
    value = home_response()
    value["buyer_query_receipt"]["response_text"] = "tampered"
    assert not verify_home_response(value)


def test_reconcile_is_create_only_and_idempotent(tmp_path: Path):
    response = home_response()
    source = tmp_path / "response.json"
    source.write_text(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state = tmp_path / "state"
    first = reconcile_response(response_path=source, state_root=state)
    second = reconcile_response(response_path=source, state_root=state)
    assert first["new_receipt"] is True
    assert second["new_receipt"] is False
    stored = state / "state/r1b-buyer-query/receipts" / f"{response['query_id']}.json"
    assert stored.read_bytes() == source.read_bytes()
    head = json.loads((state / "state/r1b-buyer-query/HEAD.json").read_text(encoding="utf-8"))
    assert head["resident_uuid"] == response["buyer_query_receipt"]["resident_uuid"]
    assert head["money_enabled"] is False
    assert head["foreign_buyer_witness"] is False


def test_reconcile_conflicting_same_query_fails(tmp_path: Path):
    response = home_response()
    source = tmp_path / "response.json"
    source.write_text(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state = tmp_path / "state"
    reconcile_response(response_path=source, state_root=state)
    target = state / "state/r1b-buyer-query/receipts" / f"{response['query_id']}.json"
    target.write_text("{}\n", encoding="utf-8")
    with pytest.raises(HomeResponseError, match="R1B_MARKET_RECEIPT_CREATE_ONLY_CONFLICT"):
        reconcile_response(response_path=source, state_root=state)
