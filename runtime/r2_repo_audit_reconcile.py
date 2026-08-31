#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

HOME_RESPONSE_SCHEMA = "janus.machine_market.home_repo_audit_response.v1"
PACKET_SCHEMA = "janus.machine_market.home_repo_audit_packet.v1"
AUDIT_RESULT_SCHEMA = "janus.market_service.repo_audit_result.v1"
DELIVERY_RECEIPT_SCHEMA = "janus.machine_market.repo_audit_delivery_receipt.v1"
QUARANTINE_SCHEMA = "janus.machine_market.repo_audit_response_quarantine.v1"

# This reconciler is deliberately restricted to the admitted owner-shadow lane.
# Expanding it to a paid lane requires a separate contract and witness.
REQUEST_ID_RE = re.compile(r"\Ara-shadow-[0-9a-f]{48}\Z")
PACKET_ID_RE = re.compile(r"\Arap-shadow-[0-9a-f]{48}\Z")
PURCHASE_ID_RE = re.compile(r"\Apur-ra-shadow-[0-9a-f]{32}\Z")
SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")
GIT_SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")
REPOSITORY_RE = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
RISK_CODE_RE = re.compile(r"\A[A-Z0-9][A-Z0-9_.:-]{0,127}\Z")
MAX_HOME_RESPONSE_BYTES = 4_000_000


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def is_request_id(value: Any) -> bool:
    return isinstance(value, str) and REQUEST_ID_RE.fullmatch(value) is not None


def require_request_id(value: Any) -> str:
    if not is_request_id(value):
        raise ValueError("REPO_AUDIT_REQUEST_ID_FORMAT_INVALID")
    return value


def expected_packet_path(request_id: Any) -> str:
    rid = require_request_id(request_id)
    return f".janus/market-home-outbox/{rid}.repo-audit.packet.json"


def expected_home_response_path(request_id: Any) -> str:
    rid = require_request_id(request_id)
    return f".janus/market-service-responses/{rid}.repo-audit-result.json"


def _valid_bounds(value: Any) -> bool:
    bounds = _mapping(value)
    if bounds is None:
        return False
    limits = {
        "max_tree_entries": (1, 10_000),
        "max_blob_files": (1, 40),
        "max_total_blob_bytes": (1, 2_000_000),
    }
    if set(bounds) != set(limits):
        return False
    return all(
        _plain_int(bounds.get(key)) and low <= bounds[key] <= high
        for key, (low, high) in limits.items()
    )


def verify_packet(packet: Mapping[str, Any]) -> bool:
    try:
        if not isinstance(packet, Mapping):
            return False
        value = dict(packet)
        claimed = value.pop("packet_hash", None)
        if not isinstance(claimed, str) or not SHA256_RE.fullmatch(claimed):
            return False
        if digest(value) != claimed:
            return False
        if value.get("schema") != PACKET_SCHEMA or value.get("sku") != "JANUS.REPO_AUDIT":
            return False
        packet_id = value.get("packet_id")
        if not isinstance(packet_id, str) or not PACKET_ID_RE.fullmatch(packet_id):
            return False
        if value.get("market_repository") != "Hawkar-usls/JANUS-MACHINE-MARKET":
            return False
        if value.get("home_repository") != "Hawkar-usls/Hawkar-usls":
            return False
        if value.get("commerce_mode") != "ZERO_PRICE_SHADOW":
            return False
        if value.get("money_enabled") is not False or value.get("payment_reference") is not None:
            return False
        for key in (
            "command_authority_granted",
            "external_effect_authorized",
            "repository_write_authorized",
            "execute_repository_code",
        ):
            if value.get(key) is not False:
                return False

        request = _mapping(value.get("service_request"))
        grant = _mapping(value.get("purchase_grant"))
        if request is None or grant is None:
            return False
        if not is_request_id(request.get("request_id")):
            return False
        if request.get("schema") != "janus.market_service.repo_audit_request.v1":
            return False
        if request.get("sku") != "JANUS.REPO_AUDIT":
            return False
        if not isinstance(request.get("buyer_actor_id"), str) or not request["buyer_actor_id"].strip():
            return False
        repository = request.get("repository")
        if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
            return False
        ref = request.get("ref")
        if not isinstance(ref, str) or not 1 <= len(ref) <= 200:
            return False
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in ref):
            return False
        if request.get("audit_scope") != "BOUNDED_STATIC_REPOSITORY_SURFACE":
            return False
        if not _valid_bounds(request.get("bounds")):
            return False
        if request.get("read_only") is not True:
            return False
        for key in (
            "execute_repository_code",
            "command_authority_granted",
            "external_effect_authorized",
        ):
            if request.get(key) is not False:
                return False

        request_copy = dict(request)
        request_hash = request_copy.pop("request_hash", None)
        if not isinstance(request_hash, str) or not SHA256_RE.fullmatch(request_hash):
            return False
        if digest(request_copy) != request_hash or value.get("service_request_hash") != request_hash:
            return False

        purchase_id = grant.get("purchase_id")
        if not isinstance(purchase_id, str) or not PURCHASE_ID_RE.fullmatch(purchase_id):
            return False
        grant_hash = value.get("purchase_grant_hash")
        if not isinstance(grant_hash, str) or not SHA256_RE.fullmatch(grant_hash):
            return False
        if digest(grant) != grant_hash:
            return False
        if grant.get("schema") != "janus.machine_market.purchase_grant.v1":
            return False
        if grant.get("sku") != "JANUS.REPO_AUDIT":
            return False
        if grant.get("status") != "PURCHASE_ELIGIBLE":
            return False
        if grant.get("execution_authority_granted") is not False:
            return False
        entitlement = _mapping(grant.get("service_entitlement"))
        if entitlement is None:
            return False
        if entitlement.get("service") != "JANUS.REPO_AUDIT":
            return False
        if entitlement.get("repository") != request.get("repository"):
            return False
        if entitlement.get("ref") != request.get("ref"):
            return False
        if entitlement.get("bounds") != request.get("bounds"):
            return False
        if entitlement.get("read_only") is not True:
            return False
        if entitlement.get("execute_repository_code") is not False:
            return False

        route = _mapping(value.get("return_route"))
        if route is None or route.get("repository") != "Hawkar-usls/JANUS-MACHINE-MARKET":
            return False
        if not _plain_int(route.get("source_issue_id")) or route["source_issue_id"] <= 0:
            return False
        if not _plain_int(route.get("source_issue_number")) or route["source_issue_number"] <= 0:
            return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def result_return_validation_errors(response: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(response, Mapping):
        return ["HOME_RESPONSE_NOT_OBJECT"]
    audit = _mapping(response.get("audit_result"))
    if audit is None:
        return ["AUDIT_RESULT_NOT_OBJECT"]

    bounds = _mapping(audit.get("bounds"))
    if bounds is None:
        errors.append("RESULT_RETURN_BOUNDS_REQUIRED")
    else:
        observed = bounds.get("observed_tree_entries")
        if not _plain_int(observed) or observed < 0:
            errors.append("RESULT_RETURN_OBSERVED_TREE_ENTRIES_INVALID")

    architecture = _mapping(audit.get("architecture_map"))
    if architecture is None:
        errors.append("RESULT_RETURN_ARCHITECTURE_MAP_REQUIRED")
    else:
        if not isinstance(architecture.get("has_tests"), bool):
            errors.append("RESULT_RETURN_HAS_TESTS_INVALID")
        if not isinstance(architecture.get("has_ci"), bool):
            errors.append("RESULT_RETURN_HAS_CI_INVALID")

    license_observations = _mapping(audit.get("license_observations"))
    if license_observations is None:
        errors.append("RESULT_RETURN_LICENSE_OBSERVATIONS_REQUIRED")
    elif not isinstance(license_observations.get("license_file_observed"), bool):
        errors.append("RESULT_RETURN_LICENSE_FILE_OBSERVED_INVALID")

    risks = audit.get("risk_register")
    if not isinstance(risks, list):
        errors.append("RESULT_RETURN_RISK_REGISTER_REQUIRED")
    else:
        for item in risks:
            row = _mapping(item)
            code = None if row is None else row.get("code")
            if not isinstance(code, str) or not RISK_CODE_RE.fullmatch(code):
                errors.append("RESULT_RETURN_RISK_CODE_INVALID")
                break
    return errors


def verify_home_response(response: Mapping[str, Any], *, packet: Mapping[str, Any]) -> bool:
    try:
        if not verify_packet(packet) or not isinstance(response, Mapping):
            return False
        request = packet["service_request"]
        grant = packet["purchase_grant"]
        request_id = response.get("service_request_id")
        if not is_request_id(request_id):
            return False

        value = dict(response)
        claimed = value.pop("home_response_hash", None)
        if not isinstance(claimed, str) or not SHA256_RE.fullmatch(claimed):
            return False
        if digest(value) != claimed:
            return False
        if value.get("schema") != HOME_RESPONSE_SCHEMA or value.get("sku") != "JANUS.REPO_AUDIT":
            return False
        if value.get("packet_id") != packet.get("packet_id"):
            return False
        if value.get("packet_hash") != packet.get("packet_hash"):
            return False
        if value.get("purchase_id") != grant.get("purchase_id"):
            return False
        if value.get("purchase_grant_hash") != packet.get("purchase_grant_hash"):
            return False
        if request_id != request.get("request_id"):
            return False
        if value.get("service_request_hash") != request.get("request_hash"):
            return False
        if value.get("commerce_mode") != packet.get("commerce_mode"):
            return False
        if value.get("money_enabled") != packet.get("money_enabled"):
            return False
        if value.get("payment_reference") != packet.get("payment_reference"):
            return False
        if value.get("same_resident_uuid") is not True:
            return False
        if value.get("return_home_verified") is not True:
            return False
        for key in (
            "model_digest",
            "file_fabric_digest",
            "runtime_receipt_hash",
            "home_service_receipt_hash",
            "audit_result_hash",
        ):
            field = value.get(key)
            if not isinstance(field, str) or not SHA256_RE.fullmatch(field):
                return False
        resident_uuid = value.get("resident_uuid")
        if not isinstance(resident_uuid, str) or not resident_uuid.strip():
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

        audit = _mapping(value.get("audit_result"))
        if audit is None:
            return False
        audit_copy = dict(audit)
        result_hash = audit_copy.pop("result_hash", None)
        if not isinstance(result_hash, str) or not SHA256_RE.fullmatch(result_hash):
            return False
        if digest(audit_copy) != result_hash or result_hash != value.get("audit_result_hash"):
            return False
        if audit.get("schema") != AUDIT_RESULT_SCHEMA:
            return False
        if audit.get("sku") != "JANUS.REPO_AUDIT":
            return False
        if audit.get("status") != "BOUNDED_REPOSITORY_AUDIT_COMPLETE":
            return False
        if audit.get("request_id") != request.get("request_id"):
            return False
        if audit.get("request_hash") != request.get("request_hash"):
            return False

        target = _mapping(audit.get("target"))
        if target is None:
            return False
        if target.get("repository") != request.get("repository"):
            return False
        if target.get("requested_ref") != request.get("ref"):
            return False
        for key in ("resolved_commit_sha", "tree_sha"):
            field = target.get(key)
            if not isinstance(field, str) or not GIT_SHA_RE.fullmatch(field):
                return False

        authority = _mapping(audit.get("authority"))
        if authority is None:
            return False
        if not all(
            (
                authority.get("read_only") is True,
                authority.get("repository_write") is False,
                authority.get("repository_code_executed") is False,
                authority.get("command_authority_granted") is False,
                authority.get("claim_authority_granted") is False,
                authority.get("scientific_evidence_authority_granted") is False,
                authority.get("world_truth_authority_granted") is False,
                authority.get("external_effect_authorized") is False,
            )
        ):
            return False

        if result_return_validation_errors(response):
            return False
        bounds = audit["bounds"]
        request_bounds = request["bounds"]
        if bounds["observed_tree_entries"] > request_bounds["max_tree_entries"]:
            return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def build_result_comment(response: Mapping[str, Any], *, packet: Mapping[str, Any]) -> str:
    if not verify_home_response(response, packet=packet):
        raise ValueError("REPO_AUDIT_RESULT_RETURN_FIELDS_INVALID")
    audit = response["audit_result"]
    target = audit["target"]
    architecture = audit["architecture_map"]
    license_observations = audit["license_observations"]
    risk_codes = ",".join(item["code"] for item in audit["risk_register"]) or "NONE"
    lines = [
        "JANUS.REPO_AUDIT verified result delivered.",
        "",
        f"- resident_uuid: `{response['resident_uuid']}`",
        f"- repository: `{target['repository']}`",
        f"- requested_ref: `{target['requested_ref']}`",
        f"- resolved_commit_sha: `{target['resolved_commit_sha']}`",
        f"- tree_sha: `{target['tree_sha']}`",
        f"- result_hash: `{response['audit_result_hash']}`",
        f"- home_response_hash: `{response['home_response_hash']}`",
        f"- observed_tree_entries: `{audit['bounds']['observed_tree_entries']}`",
        f"- tests_observed: `{str(architecture['has_tests']).lower()}`",
        f"- ci_observed: `{str(architecture['has_ci']).lower()}`",
        f"- license_file_observed: `{str(license_observations['license_file_observed']).lower()}`",
        f"- risk_codes: `{risk_codes}`",
        "- repository_code_executed: `false`",
        "- security_certification: `false`",
        "- legal_opinion: `false`",
        "",
        "The complete machine-readable audit is preserved in the Market delivery receipt/state.",
        "",
        f"<!-- REPO_AUDIT_RETURNED:{response['service_request_id']} -->",
    ]
    return "\n".join(lines) + "\n"


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
    request_id = require_request_id(packet["service_request"]["request_id"])
    if not GIT_SHA_RE.fullmatch(str(home_source_commit or "")):
        raise ValueError("REPO_AUDIT_HOME_SOURCE_COMMIT_INVALID")
    if not GIT_SHA_RE.fullmatch(str(home_response_blob_sha or "")):
        raise ValueError("REPO_AUDIT_HOME_RESPONSE_BLOB_INVALID")
    if home_response_path != expected_home_response_path(request_id):
        raise ValueError("REPO_AUDIT_HOME_RESPONSE_PATH_INVALID")
    route = packet["return_route"]
    body = {
        "schema": DELIVERY_RECEIPT_SCHEMA,
        "sku": "JANUS.REPO_AUDIT",
        "purchase_id": packet["purchase_grant"]["purchase_id"],
        "service_request_id": request_id,
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
        "source_issue_number": route["source_issue_number"],
        "result_return_fields_validated": True,
        "result_return_ready": True,
        "verified_buyer_delivery": True,
        "service_debt_closed": True,
        "repository_code_executed": False,
        "external_effect_authorized": False,
        "security_certification": False,
        "legal_opinion": False,
    }
    body["receipt_hash"] = digest(body)
    return body


def verify_market_receipt(
    receipt: Mapping[str, Any],
    *,
    response: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> bool:
    try:
        if not verify_home_response(response, packet=packet) or not isinstance(receipt, Mapping):
            return False
        value = dict(receipt)
        claimed = value.pop("receipt_hash", None)
        if not isinstance(claimed, str) or not SHA256_RE.fullmatch(claimed):
            return False
        if digest(value) != claimed:
            return False
        request_id = require_request_id(packet["service_request"]["request_id"])
        expected = {
            "schema": DELIVERY_RECEIPT_SCHEMA,
            "sku": "JANUS.REPO_AUDIT",
            "purchase_id": packet["purchase_grant"]["purchase_id"],
            "service_request_id": request_id,
            "service_request_hash": packet["service_request_hash"],
            "packet_hash": packet["packet_hash"],
            "home_response_hash": response["home_response_hash"],
            "home_service_receipt_hash": response["home_service_receipt_hash"],
            "audit_result_hash": response["audit_result_hash"],
            "resident_uuid": response["resident_uuid"],
            "resolved_commit_sha": response["audit_result"]["target"]["resolved_commit_sha"],
            "tree_sha": response["audit_result"]["target"]["tree_sha"],
            "source_issue_number": packet["return_route"]["source_issue_number"],
            "result_return_fields_validated": True,
            "result_return_ready": True,
            "verified_buyer_delivery": True,
            "service_debt_closed": True,
            "repository_code_executed": False,
            "external_effect_authorized": False,
            "security_certification": False,
            "legal_opinion": False,
        }
        if any(value.get(key) != expected_value for key, expected_value in expected.items()):
            return False
        if value.get("home_response_path") != expected_home_response_path(request_id):
            return False
        if not GIT_SHA_RE.fullmatch(str(value.get("home_source_commit") or "")):
            return False
        if not GIT_SHA_RE.fullmatch(str(value.get("home_response_git_blob_sha") or "")):
            return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def create_only_json(path: Path, value: Mapping[str, Any]) -> bool:
    rendered = pretty(value)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise ValueError("REPO_AUDIT_CREATE_ONLY_CONFLICT")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return True


def _quarantine_response(
    *,
    quarantine_dir: Path,
    source_filename: str,
    source_bytes: bytes,
    home_source_commit: str,
    reason_codes: Sequence[str],
    observed_service_request_id: Any = None,
) -> bool:
    content_sha256 = hashlib.sha256(source_bytes).hexdigest()
    observed = observed_service_request_id if isinstance(observed_service_request_id, str) else None
    observed_digest = digest(observed) if observed is not None else None
    if observed is not None and len(observed) > 256:
        observed = observed[:256]
    key = {
        "home_source_commit": home_source_commit,
        "source_filename": source_filename,
        "source_content_sha256": content_sha256,
        "reason_codes": list(reason_codes),
    }
    quarantine_id = "raq-" + digest(key)[:48]
    body: dict[str, Any] = {
        "schema": QUARANTINE_SCHEMA,
        "quarantine_id": quarantine_id,
        "status": "REJECTED_BEFORE_SELECTION",
        "source_repository": "Hawkar-usls/Hawkar-usls",
        "source_branch": "janus/market-service-responses",
        "home_source_commit": home_source_commit,
        "source_filename": source_filename,
        "source_content_bytes": len(source_bytes),
        "source_content_sha256": content_sha256,
        "observed_service_request_id": observed,
        "observed_service_request_id_sha256": observed_digest,
        "reason_codes": list(reason_codes),
        "valid_response_selected": False,
        "delivery_receipt_created": False,
        "service_debt_closed": False,
    }
    body["quarantine_record_hash"] = digest(body)
    return create_only_json(quarantine_dir / f"{quarantine_id}.json", body)


def select_oldest_verified_response(
    *,
    home_response_dir: Path,
    outbox_dir: Path,
    receipts_dir: Path,
    quarantine_dir: Path,
    stage_dir: Path,
    home_source_commit: str,
) -> dict[str, Any]:
    """Verify candidates before selection and quarantine every rejected object.

    No value read from a response is used in a path until require_request_id
    accepts its exact canonical format.
    """
    stage_dir.mkdir(parents=True, exist_ok=True)
    quarantined = 0
    quarantine_created = 0
    candidates = sorted(home_response_dir.glob("*.repo-audit-result.json")) if home_response_dir.is_dir() else []
    for response_file in candidates:
        source_bytes = response_file.read_bytes()
        response: Mapping[str, Any] | None = None
        request_id: Any = None
        reasons: list[str] = []
        if len(source_bytes) > MAX_HOME_RESPONSE_BYTES:
            reasons.append("HOME_RESPONSE_SIZE_LIMIT_EXCEEDED")
        else:
            try:
                parsed = json.loads(source_bytes.decode("utf-8"))
                response = _mapping(parsed)
                if response is None:
                    reasons.append("HOME_RESPONSE_NOT_OBJECT")
                else:
                    request_id = response.get("service_request_id")
            except (UnicodeDecodeError, json.JSONDecodeError):
                reasons.append("HOME_RESPONSE_JSON_INVALID")

        if not reasons and not is_request_id(request_id):
            reasons.append("SERVICE_REQUEST_ID_FORMAT_INVALID")

        packet: Mapping[str, Any] | None = None
        rid: str | None = None
        if not reasons:
            rid = require_request_id(request_id)
            if response_file.name != f"{rid}.repo-audit-result.json":
                reasons.append("HOME_RESPONSE_FILENAME_BINDING_INVALID")

        if not reasons and rid is not None:
            # rid has been format-validated before this path is constructed.
            packet_file = outbox_dir / f"{rid}.repo-audit.packet.json"
            if not packet_file.is_file():
                reasons.append("MARKET_PACKET_ABSENT")
            else:
                try:
                    packet = _mapping(json.loads(packet_file.read_text(encoding="utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    packet = None
                if packet is None or not verify_packet(packet):
                    reasons.append("MARKET_PACKET_INVALID")

        if not reasons and response is not None and packet is not None:
            return_errors = result_return_validation_errors(response)
            if return_errors:
                reasons.extend(return_errors)
            elif not verify_home_response(response, packet=packet):
                reasons.append("HOME_RESPONSE_SEMANTIC_INVALID")

        if reasons:
            quarantined += 1
            if _quarantine_response(
                quarantine_dir=quarantine_dir,
                source_filename=response_file.name,
                source_bytes=source_bytes,
                home_source_commit=home_source_commit,
                reason_codes=reasons,
                observed_service_request_id=request_id,
            ):
                quarantine_created += 1
            continue

        assert rid is not None and response is not None and packet is not None
        # rid was validated and the response was fully verified before this path.
        if (receipts_dir / f"{rid}.json").exists():
            continue
        (stage_dir / "home-response.json").write_text(pretty(response), encoding="utf-8")
        (stage_dir / "packet.json").write_text(pretty(packet), encoding="utf-8")
        return {
            "found": True,
            "request_id": rid,
            "home_response_path": expected_home_response_path(rid),
            "quarantined_count": quarantined,
            "quarantine_created_count": quarantine_created,
            "state_changed": quarantine_created > 0,
        }
    return {
        "found": False,
        "request_id": "",
        "home_response_path": "",
        "quarantined_count": quarantined,
        "quarantine_created_count": quarantine_created,
        "state_changed": quarantine_created > 0,
    }


__all__ = [
    "build_market_receipt",
    "build_result_comment",
    "create_only_json",
    "digest",
    "expected_home_response_path",
    "expected_packet_path",
    "is_request_id",
    "require_request_id",
    "result_return_validation_errors",
    "select_oldest_verified_response",
    "verify_home_response",
    "verify_market_receipt",
    "verify_packet",
]
