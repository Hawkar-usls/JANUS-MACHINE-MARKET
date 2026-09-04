from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.persistent_home_foreign_witness import (
    ForeignWitnessConflict,
    ForeignWitnessInvalid,
    build_ingress_claim_receipt,
    adjudicate_persistent_home_witness,
    digest,
    persist_first_witness,
    verify_witness_receipt,
)
from runtime.public_search_beta import normalize_external_issue_request
from runtime.r1b_shadow_buyer_query import build_shadow_packet
from runtime.r1b_home_response_reconcile import verify_home_response
from tests.test_r1b_home_response_reconcile import home_response

ROOT = Path(__file__).resolve().parents[1]


def policy():
    return json.loads((ROOT / "runtime/FOREIGN_AGENT_WITNESS_POLICY.json").read_text(encoding="utf-8"))


def issue(login="external-agent", uid=777001, association="NONE", issue_id=90001, number=77):
    return {
        "id": issue_id,
        "number": number,
        "created_at": "2026-09-04T01:00:00Z",
        "author_association": association,
        "user": {"login": login, "id": uid, "type": "User"},
    }


def claim(machine_client=True, surface="GITHUB_PAGES"):
    return {
        "schema": "janus.machine_market.foreign_discovery_claim.v1",
        "discovery_surface": surface,
        "independent_from_owner": True,
        "machine_client": machine_client,
    }


def bundle(discovery_surface="GITHUB_PAGES"):
    i = issue()
    raw = {
        "schema": "janus.machine_market.buyer_query_shadow_request.v1",
        "conversation_id": "external-machine-persistent-home-test",
        "turn_index": 0,
        "message_text": "Return a bounded persistent HOME witness response.",
    }
    req = normalize_external_issue_request(i, raw)
    packet = build_shadow_packet(req)
    admission = {
        "schema": "janus.machine_market.public_search_beta_admission.v1",
        "status": "ADMITTED_CREATE_ONLY",
        "request_origin": req["request_origin"],
        "buyer_actor_id": req["buyer_actor_id"],
        "source_issue_id": req["source_issue_id"],
        "source_issue_number": req["source_issue_number"],
        "query_id": packet["query_id"],
        "packet_hash": packet["packet_hash"],
        "decision": {"admitted": True, "reason": "PUBLIC_BETA_ADMITTED"},
        "money_enabled": False,
        "payment_required": False,
        "execution_authority_granted": False,
    }
    ingress = build_ingress_claim_receipt(
        issue=i,
        discovery_claim=claim(surface=discovery_surface),
        policy=policy(),
        repository_id=1352027855,
    )
    response = home_response()
    response["query_id"] = packet["query_id"]
    response["query_hash"] = packet["query_hash"]
    response["purchase_id"] = packet["purchase_grant"]["purchase_id"]
    response["purchase_grant_hash"] = packet["purchase_grant_hash"]
    response["source_packet_binding"]["market_packet_hash"] = packet["packet_hash"]
    response["return_route"] = deepcopy(packet["return_route"])
    receipt = response["buyer_query_receipt"]
    receipt["query_id"] = packet["query_id"]
    receipt["query_hash"] = packet["query_hash"]
    receipt["purchase_id"] = packet["purchase_grant"]["purchase_id"]
    receipt["purchase_grant_hash"] = packet["purchase_grant_hash"]
    response.pop("home_response_hash", None)
    response["home_response_hash"] = digest(response)
    assert verify_home_response(response)
    return i, packet, admission, ingress, response


def adjudicate(values=None):
    i, packet, admission, ingress, response = values or bundle()
    return adjudicate_persistent_home_witness(
        packet=packet,
        admission=admission,
        ingress_claim=ingress,
        home_response=response,
        current_issue=i,
        policy=policy(),
    )


def test_real_external_machine_persistent_home_bundle_passes_without_enabling_money():
    receipt = adjudicate()
    assert verify_witness_receipt(receipt)
    assert receipt["foreign_agent_witness"] is True
    assert receipt["promotion_authority"] == "PERSISTENT_RECEIPT_CANDIDATE_ONLY"
    assert receipt["money_enabled"] is False
    assert receipt["autonomous_purchase_declared"] is False
    assert receipt["paid_purchase"] is False
    assert receipt["transport"] == "PHYSARIUS_CREDENTIALLESS_PULL"
    assert receipt["closed_skus"]["JANUS.INFERENCE"].startswith("CLOSED_")
    assert receipt["closed_skus"]["JANUS.COMPUTE"].startswith("CLOSED_")


def test_global_a2a_registry_can_be_frozen_as_discovery_source_but_grants_no_authority():
    i = issue()
    ingress = build_ingress_claim_receipt(
        issue=i,
        discovery_claim=claim(surface="GLOBAL_A2A_REGISTRY"),
        policy=policy(),
        repository_id=1352027855,
    )
    assert ingress["discovery_claim"]["discovery_surface"] == "GLOBAL_A2A_REGISTRY"
    assert ingress["money_enabled"] is False
    assert ingress["autonomous_purchase_declared"] is False
    assert ingress["promotion_authority"] is False
    semantics = policy()["discovery_surface_semantics"]["GLOBAL_A2A_REGISTRY"]
    assert semantics["proves_a2a_runtime"] is False
    assert semantics["proves_execution"] is False
    assert semantics["proves_purchase_authority"] is False


def test_global_a2a_registry_discovery_still_requires_full_persistent_home_roundtrip_for_witness():
    receipt = adjudicate(bundle(discovery_surface="GLOBAL_A2A_REGISTRY"))
    assert verify_witness_receipt(receipt)
    assert receipt["discovery_claim"]["discovery_surface"] == "GLOBAL_A2A_REGISTRY"
    assert receipt["foreign_agent_witness"] is True
    assert receipt["promotion_authority"] == "PERSISTENT_RECEIPT_CANDIDATE_ONLY"
    assert receipt["money_enabled"] is False
    assert receipt["paid_purchase"] is False


def test_unknown_discovery_surface_is_rejected():
    with pytest.raises(ForeignWitnessInvalid, match="DISCOVERY_SURFACE"):
        build_ingress_claim_receipt(
            issue=issue(),
            discovery_claim=claim(surface="UNTRUSTED_RANDOM_DIRECTORY"),
            policy=policy(),
            repository_id=1352027855,
        )


def test_owner_cannot_freeze_ingress_claim():
    with pytest.raises(ForeignWitnessInvalid, match="OWNER_LOGIN"):
        build_ingress_claim_receipt(
            issue=issue(login="Hawkar-usls", uid=242020399),
            discovery_claim=claim(),
            policy=policy(),
            repository_id=1352027855,
        )


def test_non_machine_discovery_claim_cannot_promote():
    with pytest.raises(ForeignWitnessInvalid, match="MACHINE_CLIENT"):
        build_ingress_claim_receipt(
            issue=issue(),
            discovery_claim=claim(machine_client=False),
            policy=policy(),
            repository_id=1352027855,
        )


def test_spoofed_buyer_actor_is_rejected_even_with_valid_home_response_hash():
    values = list(bundle())
    packet = values[1]
    packet["buyer_query"]["buyer_actor_id"] = "github:someone-else"
    packet["buyer_query"]["query_hash"] = digest({k: v for k, v in packet["buyer_query"].items() if k != "query_hash"})
    packet["query_hash"] = packet["buyer_query"]["query_hash"]
    packet.pop("packet_hash", None)
    packet["packet_hash"] = digest(packet)
    values[2]["packet_hash"] = packet["packet_hash"]
    values[2]["query_id"] = packet["query_id"]
    response = values[4]
    response["query_hash"] = packet["query_hash"]
    response["buyer_query_receipt"]["query_hash"] = packet["query_hash"]
    response["source_packet_binding"]["market_packet_hash"] = packet["packet_hash"]
    response.pop("home_response_hash", None)
    response["home_response_hash"] = digest(response)
    with pytest.raises(ForeignWitnessInvalid):
        adjudicate(tuple(values))


def test_home_response_bound_to_different_market_packet_is_rejected():
    values = list(bundle())
    response = values[4]
    response["source_packet_binding"]["market_packet_hash"] = "f" * 64
    response.pop("home_response_hash", None)
    response["home_response_hash"] = digest(response)
    assert verify_home_response(response)
    with pytest.raises(ForeignWitnessInvalid, match="SOURCE_PACKET_HASH"):
        adjudicate(tuple(values))


def test_current_issue_identity_must_match_frozen_ingress_principal():
    values = list(bundle())
    values[0] = issue(login="different-user", uid=888002)
    with pytest.raises(ForeignWitnessInvalid, match="CURRENT_ISSUE_LOGIN"):
        adjudicate(tuple(values))


def test_public_admission_must_bind_exact_packet():
    values = list(bundle())
    values[2]["packet_hash"] = "0" * 64
    with pytest.raises(ForeignWitnessInvalid, match="ADMISSION_PACKET"):
        adjudicate(tuple(values))


def test_first_witness_persistence_is_create_only_and_exact_replay_is_idempotent(tmp_path: Path):
    receipt = adjudicate()
    first = persist_first_witness(tmp_path, receipt)
    second = persist_first_witness(tmp_path, receipt)
    assert first["receipt"] == "CREATED"
    assert first["first"] == "CREATED"
    assert second["receipt"] == "IDEMPOTENT_REPLAY"
    assert second["first"] == "IDEMPOTENT_REPLAY"


def test_second_different_first_witness_conflicts(tmp_path: Path):
    receipt = adjudicate()
    persist_first_witness(tmp_path, receipt)
    other = deepcopy(receipt)
    other["witness_id"] = "faw-home-" + "a" * 64
    body = dict(other)
    body.pop("receipt_hash", None)
    other["receipt_hash"] = digest(body)
    with pytest.raises(ForeignWitnessConflict):
        persist_first_witness(tmp_path, other)
