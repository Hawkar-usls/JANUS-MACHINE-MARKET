#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

HOME_RESPONSE_SCHEMA = "janus.machine_market.home_repo_audit_response.v1"
PACKET_SCHEMA = "janus.machine_market.home_repo_audit_packet.v1"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_packet(packet: Mapping[str, Any]) -> bool:
    if not isinstance(packet, Mapping): return False
    value=dict(packet); claimed=str(value.pop("packet_hash", ""))
    if len(claimed)!=64 or digest(value)!=claimed: return False
    if value.get("schema")!=PACKET_SCHEMA or value.get("sku")!="JANUS.REPO_AUDIT": return False
    if value.get("market_repository")!="Hawkar-usls/JANUS-MACHINE-MARKET" or value.get("home_repository")!="Hawkar-usls/Hawkar-usls": return False
    if value.get("command_authority_granted") is not False or value.get("external_effect_authorized") is not False: return False
    if value.get("repository_write_authorized") is not False or value.get("execute_repository_code") is not False: return False
    request=value.get("service_request") or {}; grant=value.get("purchase_grant") or {}; ent=grant.get("service_entitlement") or {}
    rc=dict(request); rh=str(rc.pop("request_hash", ""))
    if len(rh)!=64 or digest(rc)!=rh or value.get("service_request_hash")!=rh: return False
    if digest(grant)!=value.get("purchase_grant_hash") or grant.get("execution_authority_granted") is not False: return False
    if ent.get("service")!="JANUS.REPO_AUDIT" or ent.get("repository")!=request.get("repository") or ent.get("ref")!=request.get("ref"): return False
    return ent.get("read_only") is True and ent.get("execute_repository_code") is False


def verify_home_response(response: Mapping[str, Any], *, packet: Mapping[str, Any]) -> bool:
    if not verify_packet(packet) or not isinstance(response, Mapping): return False
    value=dict(response); claimed=str(value.pop("home_response_hash", ""))
    if len(claimed)!=64 or digest(value)!=claimed: return False
    if value.get("schema")!=HOME_RESPONSE_SCHEMA or value.get("sku")!="JANUS.REPO_AUDIT": return False
    request=packet["service_request"]; grant=packet["purchase_grant"]
    if value.get("packet_id")!=packet.get("packet_id") or value.get("packet_hash")!=packet.get("packet_hash"): return False
    if value.get("purchase_id")!=grant.get("purchase_id") or value.get("purchase_grant_hash")!=packet.get("purchase_grant_hash"): return False
    if value.get("service_request_id")!=request.get("request_id") or value.get("service_request_hash")!=request.get("request_hash"): return False
    if value.get("commerce_mode")!=packet.get("commerce_mode") or value.get("money_enabled")!=packet.get("money_enabled"): return False
    if value.get("payment_reference")!=packet.get("payment_reference"): return False
    if value.get("same_resident_uuid") is not True or value.get("return_home_verified") is not True: return False
    for key in ("model_digest","file_fabric_digest","home_service_receipt_hash","audit_result_hash"):
        if len(str(value.get(key) or "")) != 64: return False
    if not str(value.get("resident_uuid") or "").strip(): return False
    for key in ("command_authority_granted","external_effect_authorized","repository_write_authorized","repository_code_executed","security_certification_granted","legal_opinion_granted"):
        if value.get(key) is not False: return False
    audit=value.get("audit_result") or {}
    ac=dict(audit); result_hash=str(ac.pop("result_hash", ""))
    if len(result_hash)!=64 or digest(ac)!=result_hash or result_hash!=value.get("audit_result_hash"): return False
    if audit.get("schema")!="janus.market_service.repo_audit_result.v1" or audit.get("status")!="BOUNDED_REPOSITORY_AUDIT_COMPLETE": return False
    if audit.get("request_id")!=request.get("request_id") or audit.get("request_hash")!=request.get("request_hash"): return False
    target=audit.get("target") or {}
    if target.get("repository")!=request.get("repository") or target.get("requested_ref")!=request.get("ref"): return False
    if len(str(target.get("resolved_commit_sha") or ""))!=40 or len(str(target.get("tree_sha") or ""))!=40: return False
    authority=audit.get("authority") or {}
    return all([
        authority.get("read_only") is True,
        authority.get("repository_write") is False,
        authority.get("repository_code_executed") is False,
        authority.get("command_authority_granted") is False,
        authority.get("claim_authority_granted") is False,
        authority.get("scientific_evidence_authority_granted") is False,
        authority.get("world_truth_authority_granted") is False,
        authority.get("external_effect_authorized") is False,
    ])


def build_market_receipt(response: Mapping[str, Any], *, packet: Mapping[str, Any], home_source_commit: str, home_response_path: str, home_response_blob_sha: str) -> dict[str, Any]:
    if not verify_home_response(response, packet=packet):
        raise ValueError("REPO_AUDIT_HOME_RESPONSE_INVALID")
    body={
        "schema":"janus.machine_market.repo_audit_delivery_receipt.v1",
        "sku":"JANUS.REPO_AUDIT",
        "purchase_id":packet["purchase_grant"]["purchase_id"],
        "service_request_id":packet["service_request"]["request_id"],
        "service_request_hash":packet["service_request_hash"],
        "packet_hash":packet["packet_hash"],
        "home_response_hash":response["home_response_hash"],
        "home_service_receipt_hash":response["home_service_receipt_hash"],
        "audit_result_hash":response["audit_result_hash"],
        "resident_uuid":response["resident_uuid"],
        "resolved_commit_sha":response["audit_result"]["target"]["resolved_commit_sha"],
        "tree_sha":response["audit_result"]["target"]["tree_sha"],
        "home_source_commit":home_source_commit,
        "home_response_path":home_response_path,
        "home_response_git_blob_sha":home_response_blob_sha,
        "verified_buyer_delivery":True,
        "service_debt_closed":True,
        "repository_code_executed":False,
        "external_effect_authorized":False,
        "security_certification":False,
        "legal_opinion":False,
    }
    body["receipt_hash"]=digest(body)
    return body


__all__=["build_market_receipt","digest","verify_home_response","verify_packet"]
