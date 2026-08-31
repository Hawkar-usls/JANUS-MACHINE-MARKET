#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

HOME_RESPONSE_SCHEMA = "janus.machine_market.home_dataset_scout_response.v1"
PACKET_SCHEMA = "janus.machine_market.home_dataset_scout_packet.v1"
RESULT_SCHEMA = "janus.market_service.dataset_scout_result.v1"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_packet(packet: Mapping[str, Any]) -> bool:
    try:
        value = dict(packet); claimed = str(value.pop("packet_hash", ""))
        if len(claimed) != 64 or digest(value) != claimed:
            return False
        if value.get("schema") != PACKET_SCHEMA or value.get("sku") != "JANUS.DATASET_SCOUT":
            return False
        if value.get("market_repository") != "Hawkar-usls/JANUS-MACHINE-MARKET" or value.get("home_repository") != "Hawkar-usls/Hawkar-usls":
            return False
        if value.get("commerce_mode") != "ZERO_PRICE_SHADOW" or value.get("money_enabled") is not False or value.get("payment_reference") is not None:
            return False
        for key in ("command_authority_granted", "external_effect_authorized", "dataset_payload_download_authorized", "redistribution_authority_granted"):
            if value.get(key) is not False:
                return False
        request = value.get("service_request") or {}; rc = dict(request); request_hash = str(rc.pop("request_hash", ""))
        if len(request_hash) != 64 or digest(rc) != request_hash or value.get("service_request_hash") != request_hash:
            return False
        if request.get("sku") != "JANUS.DATASET_SCOUT" or not str(request.get("query") or "").strip() or request.get("read_only") is not True:
            return False
        grant = value.get("purchase_grant") or {}; ent = grant.get("service_entitlement") or {}
        if digest(grant) != value.get("purchase_grant_hash") or grant.get("execution_authority_granted") is not False:
            return False
        return all([
            ent.get("service") == "JANUS.DATASET_SCOUT",
            ent.get("request_id") == request.get("request_id"),
            ent.get("bounds") == request.get("bounds"),
            ent.get("read_only") is True,
            ent.get("dataset_payload_download_authorized") is False,
            ent.get("redistribution_authority_granted") is False,
        ])
    except Exception:
        return False


def verify_home_response(response: Mapping[str, Any], *, packet: Mapping[str, Any]) -> bool:
    try:
        if not verify_packet(packet) or not isinstance(response, Mapping):
            return False
        value = dict(response); claimed = str(value.pop("home_response_hash", ""))
        if len(claimed) != 64 or digest(value) != claimed:
            return False
        if value.get("schema") != HOME_RESPONSE_SCHEMA or value.get("sku") != "JANUS.DATASET_SCOUT":
            return False
        request = packet["service_request"]; grant = packet["purchase_grant"]
        if value.get("packet_id") != packet.get("packet_id") or value.get("packet_hash") != packet.get("packet_hash"):
            return False
        if value.get("purchase_id") != grant.get("purchase_id") or value.get("purchase_grant_hash") != packet.get("purchase_grant_hash"):
            return False
        if value.get("service_request_id") != request.get("request_id") or value.get("service_request_hash") != request.get("request_hash"):
            return False
        if value.get("commerce_mode") != packet.get("commerce_mode") or value.get("money_enabled") != packet.get("money_enabled") or value.get("payment_reference") != packet.get("payment_reference"):
            return False
        if value.get("same_resident_uuid") is not True or value.get("return_home_verified") is not True:
            return False
        for key in ("model_digest", "file_fabric_digest", "home_service_receipt_hash", "dataset_scout_result_hash"):
            if len(str(value.get(key) or "")) != 64:
                return False
        if not str(value.get("resident_uuid") or "").strip():
            return False
        for key in ("command_authority_granted", "external_effect_authorized", "dataset_payload_downloaded", "redistribution_authority_granted", "license_authority_granted"):
            if value.get(key) is not False:
                return False
        result = value.get("dataset_scout_result") or {}; rc = dict(result); result_hash = str(rc.pop("result_hash", ""))
        if len(result_hash) != 64 or digest(rc) != result_hash or result_hash != value.get("dataset_scout_result_hash"):
            return False
        if result.get("schema") != RESULT_SCHEMA or result.get("status") != "BOUNDED_DATASET_SCOUT_COMPLETE":
            return False
        if result.get("request_id") != request.get("request_id") or result.get("request_hash") != request.get("request_hash"):
            return False
        authority = result.get("authority") or {}
        if not all([
            authority.get("read_only") is True,
            authority.get("dataset_payload_downloaded") is False,
            authority.get("redistribution_authority_granted") is False,
            authority.get("license_authority_granted") is False,
            authority.get("command_authority_granted") is False,
            authority.get("external_effect_authorized") is False,
        ]):
            return False
        manifest = result.get("dataset_manifest")
        return isinstance(manifest, list) and len(manifest) >= 1
    except Exception:
        return False


def build_market_receipt(response: Mapping[str, Any], *, packet: Mapping[str, Any], home_source_commit: str, home_response_path: str, home_response_blob_sha: str) -> dict[str, Any]:
    if not verify_home_response(response, packet=packet):
        raise ValueError("DATASET_SCOUT_HOME_RESPONSE_INVALID")
    result = response["dataset_scout_result"]
    body = {
        "schema": "janus.machine_market.dataset_scout_delivery_receipt.v1",
        "sku": "JANUS.DATASET_SCOUT",
        "purchase_id": packet["purchase_grant"]["purchase_id"],
        "service_request_id": packet["service_request"]["request_id"],
        "service_request_hash": packet["service_request_hash"],
        "packet_hash": packet["packet_hash"],
        "home_response_hash": response["home_response_hash"],
        "home_service_receipt_hash": response["home_service_receipt_hash"],
        "dataset_scout_result_hash": response["dataset_scout_result_hash"],
        "resident_uuid": response["resident_uuid"],
        "candidate_count": len(result["dataset_manifest"]),
        "catalogs_succeeded": result["provenance"]["catalogs_succeeded"],
        "home_source_commit": home_source_commit,
        "home_response_path": home_response_path,
        "home_response_git_blob_sha": home_response_blob_sha,
        "verified_buyer_delivery": True,
        "service_debt_closed": True,
        "dataset_payload_downloaded": False,
        "redistribution_authority_granted": False,
        "license_authority_granted": False,
        "external_effect_authorized": False,
    }
    body["receipt_hash"] = digest(body)
    return body


__all__ = ["build_market_receipt", "digest", "verify_home_response", "verify_packet"]
