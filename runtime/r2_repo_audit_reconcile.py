#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

HOME_RESPONSE_SCHEMA = "janus.machine_market.home_repo_audit_response.v1"
PACKET_SCHEMA = "janus.machine_market.home_repo_audit_packet.v1"
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
RISK_CODE_RE = re.compile(r"^[A-Z0-9_]{1,96}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_safe_identifier(value: Any) -> bool:
    return isinstance(value, str) and SAFE_IDENTIFIER_RE.fullmatch(value) is not None


def _is_hex40(value: Any) -> bool:
    return isinstance(value, str) and HEX40_RE.fullmatch(value) is not None


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and HEX64_RE.fullmatch(value) is not None


def prevalidate_home_response_identity(response: Any) -> str | None:
    """Validate schema + identity syntax before any identity-derived filesystem path exists."""
    if not isinstance(response, Mapping):
        return None
    if response.get("schema") != HOME_RESPONSE_SCHEMA or response.get("sku") != "JANUS.REPO_AUDIT":
        return None
    request_id = response.get("service_request_id")
    if not is_safe_identifier(request_id):
        return None
    if not _is_hex64(response.get("service_request_hash")) or not _is_hex64(response.get("packet_hash")):
        return None
    return request_id


def _valid_result_return_fields(audit: Mapping[str, Any]) -> bool:
    """Validate every structure consumed by the result-return step before delivery is persisted."""
    architecture = audit.get("architecture_map")
    licenses = audit.get("license_observations")
    bounds = audit.get("bounds")
    risks = audit.get("risk_register")
    if not isinstance(architecture, Mapping) or not isinstance(licenses, Mapping) or not isinstance(bounds, Mapping):
        return False
    if not isinstance(risks, list):
        return False
    if not isinstance(architecture.get("has_tests"), bool) or not isinstance(architecture.get("has_ci"), bool):
        return False
    if not isinstance(licenses.get("license_file_observed"), bool):
        return False
    observed = bounds.get("observed_tree_entries")
    if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
        return False
    for risk in risks:
        if not isinstance(risk, Mapping):
            return False
        code = risk.get("code")
        if not isinstance(code, str) or RISK_CODE_RE.fullmatch(code) is None:
            return False
    return True


def verify_packet(packet: Mapping[str, Any]) -> bool:
    if not isinstance(packet, Mapping):
        return False
    value = dict(packet)
    claimed = value.pop("packet_hash", "")
    if not _is_hex64(claimed) or digest(value) != claimed:
        return False
    if value.get("schema") != PACKET_SCHEMA or value.get("sku") != "JANUS.REPO_AUDIT":
        return False
    if value.get("market_repository") != "Hawkar-usls/JANUS-MACHINE-MARKET" or value.get("home_repository") != "Hawkar-usls/Hawkar-usls":
        return False
    if value.get("command_authority_granted") is not False or value.get("external_effect_authorized") is not False:
        return False
    if value.get("repository_write_authorized") is not False or value.get("execute_repository_code") is not False:
        return False

    request = value.get("service_request") or {}
    grant = value.get("purchase_grant") or {}
    ent = grant.get("service_entitlement") or {}
    if not isinstance(request, Mapping) or not isinstance(grant, Mapping) or not isinstance(ent, Mapping):
        return False
    if not is_safe_identifier(request.get("request_id")):
        return False

    request_copy = dict(request)
    request_hash = request_copy.pop("request_hash", "")
    if not _is_hex64(request_hash) or digest(request_copy) != request_hash or value.get("service_request_hash") != request_hash:
        return False
    if digest(grant) != value.get("purchase_grant_hash") or grant.get("execution_authority_granted") is not False:
        return False
    if ent.get("service") != "JANUS.REPO_AUDIT" or ent.get("repository") != request.get("repository") or ent.get("ref") != request.get("ref"):
        return False
    if ent.get("read_only") is not True or ent.get("execute_repository_code") is not False:
        return False

    route = value.get("return_route") or {}
    if route and not isinstance(route, Mapping):
        return False
    if route:
        if route.get("repository") != "Hawkar-usls/JANUS-MACHINE-MARKET":
            return False
        issue_number = route.get("source_issue_number")
        if issue_number is not None and (isinstance(issue_number, bool) or not isinstance(issue_number, int) or issue_number <= 0):
            return False
    return True


def verify_home_response(response: Mapping[str, Any], *, packet: Mapping[str, Any]) -> bool:
    if not verify_packet(packet) or prevalidate_home_response_identity(response) is None:
        return False
    value = dict(response)
    claimed = value.pop("home_response_hash", "")
    if not _is_hex64(claimed) or digest(value) != claimed:
        return False

    request = packet["service_request"]
    grant = packet["purchase_grant"]
    if value.get("packet_id") != packet.get("packet_id") or value.get("packet_hash") != packet.get("packet_hash"):
        return False
    if value.get("purchase_id") != grant.get("purchase_id") or value.get("purchase_grant_hash") != packet.get("purchase_grant_hash"):
        return False
    if value.get("service_request_id") != request.get("request_id") or value.get("service_request_hash") != request.get("request_hash"):
        return False
    if value.get("commerce_mode") != packet.get("commerce_mode") or value.get("money_enabled") != packet.get("money_enabled"):
        return False
    if value.get("payment_reference") != packet.get("payment_reference"):
        return False
    if value.get("same_resident_uuid") is not True or value.get("return_home_verified") is not True:
        return False
    for key in ("model_digest", "file_fabric_digest", "home_service_receipt_hash", "audit_result_hash"):
        if not _is_hex64(value.get(key)):
            return False
    if not str(value.get("resident_uuid") or "").strip():
        return False
    for key in (
        "command_authority_granted",
        "external_effect_authorized",
        "repository_write_authorized",
        "repository_code_executed",
        "security_certification_granted",
        "legal_opinion_granted",
    ):
        if value.get(key) is not False:
            return False

    audit = value.get("audit_result")
    if not isinstance(audit, Mapping):
        return False
    audit_copy = dict(audit)
    result_hash = audit_copy.pop("result_hash", "")
    if not _is_hex64(result_hash) or digest(audit_copy) != result_hash or result_hash != value.get("audit_result_hash"):
        return False
    if audit.get("schema") != "janus.market_service.repo_audit_result.v1" or audit.get("status") != "BOUNDED_REPOSITORY_AUDIT_COMPLETE":
        return False
    if audit.get("request_id") != request.get("request_id") or audit.get("request_hash") != request.get("request_hash"):
        return False

    target = audit.get("target")
    if not isinstance(target, Mapping):
        return False
    if target.get("repository") != request.get("repository") or target.get("requested_ref") != request.get("ref"):
        return False
    if not _is_hex40(target.get("resolved_commit_sha")) or not _is_hex40(target.get("tree_sha")):
        return False
    if not _valid_result_return_fields(audit):
        return False

    authority = audit.get("authority") or {}
    if not isinstance(authority, Mapping):
        return False
    return all(
        [
            authority.get("read_only") is True,
            authority.get("repository_write") is False,
            authority.get("repository_code_executed") is False,
            authority.get("command_authority_granted") is False,
            authority.get("claim_authority_granted") is False,
            authority.get("scientific_evidence_authority_granted") is False,
            authority.get("world_truth_authority_granted") is False,
            authority.get("external_effect_authorized") is False,
        ]
    )


def build_market_receipt(
    response: Mapping[str, Any],
    *,
    packet: Mapping[str, Any],
    home_source_commit: str,
    home_response_path: str,
    home_response_blob_sha: str,
) -> dict[str, Any]:
    if not verify_home_response(response, packet=packet):
        raise ValueError("REPO_AUDIT_HOME_RESPONSE_INVALID")
    if not _is_hex40(home_source_commit) or not _is_hex40(home_response_blob_sha):
        raise ValueError("REPO_AUDIT_HOME_SOURCE_BINDING_INVALID")
    expected_suffix = f"/{packet['service_request']['request_id']}.repo-audit-result.json"
    if not isinstance(home_response_path, str) or not home_response_path.endswith(expected_suffix):
        raise ValueError("REPO_AUDIT_HOME_RESPONSE_PATH_BINDING_INVALID")

    body = {
        "schema": "janus.machine_market.repo_audit_delivery_receipt.v1",
        "sku": "JANUS.REPO_AUDIT",
        "purchase_id": packet["purchase_grant"]["purchase_id"],
        "service_request_id": packet["service_request"]["request_id"],
        "service_request_hash": packet["service_request_hash"],
        "packet_hash": packet["packet_hash"],
        "home_response_hash": response["home_response_hash"],
        "home_service_receipt_hash": response["home_service_receipt_hash"],
        "audit_result_hash": response["audit_result_hash"],
        "resident_uuid": response["resident_uuid"],
        "resolved_commit_sha": response["audit_result"]["target"]["resolved_commit_sha"],
        "tree_sha": response["audit_result"]["target"]["tree_sha"],
        "home_source_commit": home_source_commit,
        "home_response_path": home_response_path,
        "home_response_git_blob_sha": home_response_blob_sha,
        "verified_buyer_delivery": True,
        "service_debt_closed": True,
        "repository_code_executed": False,
        "external_effect_authorized": False,
        "security_certification": False,
        "legal_opinion": False,
    }
    body["receipt_hash"] = digest(body)
    return body


__all__ = [
    "build_market_receipt",
    "digest",
    "is_safe_identifier",
    "prevalidate_home_response_identity",
    "verify_home_response",
    "verify_packet",
]
