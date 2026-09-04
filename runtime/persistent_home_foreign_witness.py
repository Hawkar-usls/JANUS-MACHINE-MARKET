#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from runtime.r1b_home_response_reconcile import ZERO_MODE, verify_home_response
from runtime.r1b_shadow_buyer_query import verify_shadow_packet

PUBLIC_ORIGIN = "FOREIGN_PUBLIC_ZERO_PRICE_BETA"
DISCOVERY_SCHEMA = "janus.machine_market.foreign_discovery_claim.v1"
INGRESS_CLAIM_SCHEMA = "janus.machine_market.public_search_foreign_witness_claim.v1"
ADMISSION_SCHEMA = "janus.machine_market.public_search_beta_admission.v1"
WITNESS_SCHEMA = "janus.machine_market.persistent_home_foreign_agent_witness_receipt.v1"
FIRST_SCHEMA = "janus.machine_market.persistent_home_foreign_agent_witness_first.v1"


class ForeignWitnessInvalid(ValueError):
    pass


class ForeignWitnessConflict(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ForeignWitnessInvalid(code)


def _issue_principal(issue: Mapping[str, Any]) -> dict[str, Any]:
    user = issue.get("user") or {}
    login = str(user.get("login") or "").strip()
    uid = int(user.get("id") or 0)
    utype = str(user.get("type") or "").strip()
    association = str(issue.get("author_association") or "NONE").upper()
    issue_id = int(issue.get("id") or 0)
    issue_number = int(issue.get("number") or 0)
    require(bool(login) and uid > 0 and bool(utype), "FOREIGN_WITNESS_ISSUE_PRINCIPAL_INVALID")
    require(issue_id > 0 and issue_number > 0, "FOREIGN_WITNESS_ISSUE_IDENTITY_INVALID")
    return {
        "login": login,
        "github_user_id": uid,
        "type": utype,
        "author_association": association,
        "issue_id": issue_id,
        "issue_number": issue_number,
    }


def _validate_principal(principal: Mapping[str, Any], policy: Mapping[str, Any]) -> None:
    owner = policy.get("owner") or {}
    gate = policy.get("independence_gate") or {}
    require(str(principal.get("login") or "").lower() != str(owner.get("login") or "").lower(), "FOREIGN_WITNESS_OWNER_LOGIN_REJECTED")
    require(int(principal.get("github_user_id") or 0) != int(owner.get("github_user_id") or 0), "FOREIGN_WITNESS_OWNER_ID_REJECTED")
    require(str(principal.get("type") or "").lower() != "bot", "FOREIGN_WITNESS_BOT_REJECTED")
    allowed = {str(x).upper() for x in gate.get("accepted_author_association") or []}
    require(str(principal.get("author_association") or "").upper() in allowed, "FOREIGN_WITNESS_AUTHOR_ASSOCIATION_REJECTED")


def validate_discovery_claim(claim: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    required = policy.get("required_discovery_claim") or {}
    value = dict(claim)
    require(value.get("schema") == required.get("schema") == DISCOVERY_SCHEMA, "FOREIGN_DISCOVERY_SCHEMA_REJECTED")
    require(value.get("discovery_surface") in set(required.get("allowed_surfaces") or []), "FOREIGN_DISCOVERY_SURFACE_REJECTED")
    require(value.get("independent_from_owner") is True, "FOREIGN_DISCOVERY_INDEPENDENCE_ATTESTATION_REQUIRED")
    require(value.get("machine_client") is True, "FOREIGN_DISCOVERY_MACHINE_CLIENT_ATTESTATION_REQUIRED")
    return value


def build_ingress_claim_receipt(*, issue: Mapping[str, Any], discovery_claim: Mapping[str, Any], policy: Mapping[str, Any], repository_id: int) -> dict[str, Any]:
    principal = _issue_principal(issue)
    _validate_principal(principal, policy)
    claim = validate_discovery_claim(discovery_claim, policy)
    require(int(repository_id) > 0, "FOREIGN_WITNESS_REPOSITORY_ID_INVALID")
    body = {
        "schema": INGRESS_CLAIM_SCHEMA,
        "status": "INGRESS_CLAIM_FROZEN_BEFORE_HOME_RESULT",
        "repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
        "repository_id": int(repository_id),
        "issue_id": principal["issue_id"],
        "issue_number": principal["issue_number"],
        "requester": {
            "login": principal["login"],
            "github_user_id": principal["github_user_id"],
            "type": principal["type"],
            "author_association": principal["author_association"],
        },
        "issue_created_at": str(issue.get("created_at") or ""),
        "discovery_claim": claim,
        "discovery_claim_hash": digest(claim),
        "money_enabled": False,
        "autonomous_purchase_declared": False,
        "promotion_authority": False,
    }
    return {**body, "receipt_hash": digest(body)}


def verify_ingress_claim_receipt(receipt: Mapping[str, Any], policy: Mapping[str, Any]) -> bool:
    try:
        value = dict(receipt)
        claimed = str(value.pop("receipt_hash", ""))
        if len(claimed) != 64 or digest(value) != claimed:
            return False
        if value.get("schema") != INGRESS_CLAIM_SCHEMA or value.get("status") != "INGRESS_CLAIM_FROZEN_BEFORE_HOME_RESULT":
            return False
        if value.get("money_enabled") is not False or value.get("autonomous_purchase_declared") is not False or value.get("promotion_authority") is not False:
            return False
        principal = dict(value.get("requester") or {})
        principal["issue_id"] = value.get("issue_id")
        principal["issue_number"] = value.get("issue_number")
        _validate_principal(principal, policy)
        claim = validate_discovery_claim(value.get("discovery_claim") or {}, policy)
        return value.get("discovery_claim_hash") == digest(claim)
    except (ForeignWitnessInvalid, TypeError, ValueError):
        return False


def adjudicate_persistent_home_witness(
    *,
    packet: Mapping[str, Any],
    admission: Mapping[str, Any],
    ingress_claim: Mapping[str, Any],
    home_response: Mapping[str, Any],
    current_issue: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    packet = dict(packet)
    admission = dict(admission)
    ingress_claim = dict(ingress_claim)
    response = dict(home_response)
    issue_principal = _issue_principal(current_issue)

    require(verify_shadow_packet(packet), "FOREIGN_WITNESS_PACKET_INVALID")
    require(verify_home_response(response), "FOREIGN_WITNESS_HOME_RESPONSE_INVALID")
    require(verify_ingress_claim_receipt(ingress_claim, policy), "FOREIGN_WITNESS_INGRESS_CLAIM_INVALID")
    require(packet.get("mode") == ZERO_MODE, "FOREIGN_WITNESS_REQUIRES_ZERO_PRICE_DISCOVERY_RUN")
    require(packet.get("request_origin") == PUBLIC_ORIGIN, "FOREIGN_WITNESS_PUBLIC_ORIGIN_REQUIRED")
    require(packet.get("money_enabled") is False and packet.get("payment_required") is False, "FOREIGN_WITNESS_PREPAYMENT_REQUIRED_FALSE")
    require(response.get("mode") == ZERO_MODE and response.get("money_enabled") is False, "FOREIGN_WITNESS_HOME_RESPONSE_MUST_BE_ZERO_PRICE")

    query = packet.get("buyer_query") or {}
    route = packet.get("return_route") or {}
    response_route = response.get("return_route") or {}
    source = response.get("source_packet_binding") or {}
    principal = ingress_claim.get("requester") or {}
    issue_id = int(ingress_claim.get("issue_id") or 0)
    issue_number = int(ingress_claim.get("issue_number") or 0)

    require(response.get("query_id") == packet.get("query_id"), "FOREIGN_WITNESS_QUERY_ID_MISMATCH")
    require(response.get("query_hash") == packet.get("query_hash"), "FOREIGN_WITNESS_QUERY_HASH_MISMATCH")
    require(response.get("purchase_id") == (packet.get("purchase_grant") or {}).get("purchase_id"), "FOREIGN_WITNESS_PURCHASE_ID_MISMATCH")
    require(response.get("purchase_grant_hash") == packet.get("purchase_grant_hash"), "FOREIGN_WITNESS_GRANT_HASH_MISMATCH")
    require(source.get("market_packet_hash") == packet.get("packet_hash"), "FOREIGN_WITNESS_SOURCE_PACKET_HASH_MISMATCH")
    require(source.get("transport") == "PHYSARIUS_CREDENTIALLESS_PULL", "FOREIGN_WITNESS_TRANSPORT_MISMATCH")
    require(int(route.get("source_issue_id") or 0) == issue_id and int(route.get("source_issue_number") or 0) == issue_number, "FOREIGN_WITNESS_PACKET_ISSUE_BINDING_MISMATCH")
    require(int(response_route.get("source_issue_id") or 0) == issue_id and int(response_route.get("source_issue_number") or 0) == issue_number, "FOREIGN_WITNESS_RESPONSE_ISSUE_BINDING_MISMATCH")

    require(admission.get("schema") == ADMISSION_SCHEMA and admission.get("status") == "ADMITTED_CREATE_ONLY", "FOREIGN_WITNESS_PUBLIC_ADMISSION_INVALID")
    require(admission.get("request_origin") == PUBLIC_ORIGIN, "FOREIGN_WITNESS_ADMISSION_ORIGIN_INVALID")
    require(int(admission.get("source_issue_id") or 0) == issue_id and int(admission.get("source_issue_number") or 0) == issue_number, "FOREIGN_WITNESS_ADMISSION_ISSUE_MISMATCH")
    require(admission.get("query_id") == packet.get("query_id") and admission.get("packet_hash") == packet.get("packet_hash"), "FOREIGN_WITNESS_ADMISSION_PACKET_MISMATCH")
    require(admission.get("money_enabled") is False and admission.get("payment_required") is False, "FOREIGN_WITNESS_ADMISSION_MONEY_MUST_BE_FALSE")

    _validate_principal({**principal, "issue_id": issue_id, "issue_number": issue_number}, policy)
    require(issue_principal["login"].lower() == str(principal.get("login") or "").lower(), "FOREIGN_WITNESS_CURRENT_ISSUE_LOGIN_MISMATCH")
    require(issue_principal["github_user_id"] == int(principal.get("github_user_id") or 0), "FOREIGN_WITNESS_CURRENT_ISSUE_ID_MISMATCH")
    require(issue_principal["type"].lower() == str(principal.get("type") or "").lower(), "FOREIGN_WITNESS_CURRENT_ISSUE_TYPE_MISMATCH")
    require(str(query.get("buyer_actor_id") or "").lower() == f"github:{principal['login']}".lower(), "FOREIGN_WITNESS_BUYER_ACTOR_MISMATCH")
    require(str(admission.get("buyer_actor_id") or "").lower() == f"github:{principal['login']}".lower(), "FOREIGN_WITNESS_ADMISSION_ACTOR_MISMATCH")

    receipt = response.get("buyer_query_receipt") or {}
    require(receipt.get("status") in {"DELIVERED", "REPLAYED"}, "FOREIGN_WITNESS_HOME_DELIVERY_STATUS_INVALID")
    require(bool(receipt.get("resident_uuid")) and bool(receipt.get("execution_identity")) and bool(receipt.get("response_hash")), "FOREIGN_WITNESS_PERSISTENT_RESULT_BINDING_MISSING")
    require(receipt.get("billable_execution_delta") == 0, "FOREIGN_WITNESS_DISCOVERY_RUN_MUST_NOT_BE_BILLABLE")

    seed = {
        "repository_id": int(ingress_claim.get("repository_id") or 0),
        "issue_id": issue_id,
        "requester_github_user_id": int(principal.get("github_user_id") or 0),
        "query_id": packet["query_id"],
        "packet_hash": packet["packet_hash"],
        "home_response_hash": response["home_response_hash"],
    }
    witness_id = "faw-home-" + digest(seed)
    body = {
        "schema": WITNESS_SCHEMA,
        "status": "FOREIGN_PERSISTENT_HOME_WITNESS_OBSERVED_UNDER_GITHUB_TRUST_MODEL",
        "witness_id": witness_id,
        "foreign_agent_witness": True,
        "promotion_authority": "PERSISTENT_RECEIPT_CANDIDATE_ONLY",
        "repository": ingress_claim.get("repository"),
        "repository_id": int(ingress_claim.get("repository_id") or 0),
        "issue_id": issue_id,
        "issue_number": issue_number,
        "requester": dict(principal),
        "discovery_claim": dict(ingress_claim.get("discovery_claim") or {}),
        "discovery_claim_hash": ingress_claim.get("discovery_claim_hash"),
        "ingress_claim_receipt_hash": ingress_claim.get("receipt_hash"),
        "public_admission": {
            "query_id": admission.get("query_id"),
            "packet_hash": admission.get("packet_hash"),
            "buyer_actor_id": admission.get("buyer_actor_id"),
        },
        "request_origin": PUBLIC_ORIGIN,
        "request_hash": packet.get("request_hash"),
        "query_id": packet.get("query_id"),
        "query_hash": packet.get("query_hash"),
        "purchase_id": response.get("purchase_id"),
        "purchase_grant_hash": response.get("purchase_grant_hash"),
        "market_packet_hash": packet.get("packet_hash"),
        "market_source_commit": source.get("market_source_commit"),
        "market_packet_git_blob_sha": source.get("market_packet_git_blob_sha"),
        "pull_receipt_hash": source.get("pull_receipt_hash"),
        "transport": source.get("transport"),
        "home_response_hash": response.get("home_response_hash"),
        "resident_uuid": receipt.get("resident_uuid"),
        "model_digest": receipt.get("model_digest"),
        "file_fabric_digest": receipt.get("file_fabric_digest"),
        "hrain_context_receipt_hash": receipt.get("hrain_context_receipt_hash"),
        "execution_identity": receipt.get("execution_identity"),
        "response_hash": receipt.get("response_hash"),
        "money_enabled": False,
        "autonomous_purchase_declared": False,
        "paid_purchase": False,
        "closed_skus": {
            "JANUS.INFERENCE": "CLOSED_TARGET_EXECUTION_WITNESS_PENDING",
            "JANUS.COMPUTE": "CLOSED_TARGET_EXECUTION_WITNESS_PENDING",
        },
        "trust_boundary": "GITHUB_OBSERVABLE_EXTERNAL_PRINCIPAL_PLUS_FROZEN_MACHINE_DISCOVERY_CLAIM_PLUS_PERSISTENT_HOME_RESULT",
    }
    return {**body, "receipt_hash": digest(body)}


def verify_witness_receipt(receipt: Mapping[str, Any]) -> bool:
    try:
        value = dict(receipt)
        claimed = str(value.pop("receipt_hash", ""))
        if len(claimed) != 64 or digest(value) != claimed:
            return False
        return (
            value.get("schema") == WITNESS_SCHEMA
            and value.get("foreign_agent_witness") is True
            and value.get("money_enabled") is False
            and value.get("autonomous_purchase_declared") is False
            and value.get("paid_purchase") is False
            and value.get("promotion_authority") == "PERSISTENT_RECEIPT_CANDIDATE_ONLY"
            and value.get("request_origin") == PUBLIC_ORIGIN
            and value.get("transport") == "PHYSARIUS_CREDENTIALLESS_PULL"
            and bool(value.get("home_response_hash"))
            and bool(value.get("execution_identity"))
        )
    except Exception:
        return False


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
        raise ForeignWitnessConflict(f"conflicting create-only witness record: {path}")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return "CREATED"


def persist_first_witness(state_root: str | Path, receipt: Mapping[str, Any]) -> dict[str, str]:
    value = dict(receipt)
    require(verify_witness_receipt(value), "FOREIGN_WITNESS_RECEIPT_INVALID")
    root = Path(state_root) / "state/r1-foreign-home"
    receipt_path = root / "receipts" / f"{value['witness_id']}.json"
    first = {
        "schema": FIRST_SCHEMA,
        "status": "FIRST_QUALIFYING_PERSISTENT_HOME_FOREIGN_AGENT_WITNESS",
        "witness_id": value["witness_id"],
        "receipt_hash": value["receipt_hash"],
        "requester": value["requester"],
        "query_id": value["query_id"],
        "home_response_hash": value["home_response_hash"],
        "foreign_agent_witness": True,
        "money_enabled": False,
        "promotion_required": True,
    }
    receipt_status = _create_only(receipt_path, value)
    try:
        first_status = _create_only(root / "FIRST.json", first)
    except Exception:
        if receipt_status == "CREATED":
            receipt_path.unlink(missing_ok=True)
        raise
    return {
        "receipt": receipt_status,
        "first": first_status,
        "receipt_path": str(receipt_path),
        "first_path": str(root / "FIRST.json"),
    }
