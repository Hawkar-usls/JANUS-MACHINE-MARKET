#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REQUEST_SCHEMA = "janus.market_service.dataset_scout_request.v1"
PACKET_SCHEMA = "janus.machine_market.home_dataset_scout_packet.v1"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _strings(value: Any, *, limit: int, item_limit: int) -> list[str]:
    if value is None:
        return []
    require(isinstance(value, list), "DATASET_SCOUT_PREFERENCE_LIST_REQUIRED")
    out: list[str] = []
    for item in value[:limit]:
        text = str(item or "").strip()
        if text:
            out.append(text[:item_limit])
    return out


def build_shadow_packet(request: Mapping[str, Any]) -> dict[str, Any]:
    buyer = str(request.get("buyer_actor_id") or "").strip()
    query = str(request.get("query") or "").strip()
    domain = str(request.get("domain") or "").strip()[:200]
    created_at = str(request.get("created_at") or "").strip()
    source_issue_id = request.get("source_issue_id")
    source_issue_number = request.get("source_issue_number")
    require(bool(buyer and query and created_at), "DATASET_SCOUT_PROVENANCE_REQUIRED")
    require(len(query) <= 500, "DATASET_SCOUT_QUERY_TOO_LONG")
    require(isinstance(source_issue_id, int) and not isinstance(source_issue_id, bool), "DATASET_SCOUT_SOURCE_ISSUE_ID_REQUIRED")

    license_preferences = _strings(request.get("license_preferences"), limit=20, item_limit=120)
    format_preferences = _strings(request.get("format_preferences"), limit=20, item_limit=80)
    bounds = {
        "max_results": min(max(int(request.get("max_results", 8)), 1), 20),
        "max_catalogs": min(max(int(request.get("max_catalogs", 2)), 1), 2),
        "per_catalog_timeout_seconds": min(max(int(request.get("per_catalog_timeout_seconds", 8)), 2), 15),
    }
    request_id = "ds-shadow-" + digest({
        "source_issue_id": source_issue_id,
        "buyer_actor_id": buyer,
        "query": query,
        "domain": domain,
        "date_range": request.get("date_range"),
        "license_preferences": license_preferences,
        "format_preferences": format_preferences,
        "bounds": bounds,
    })[:48]
    service_request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "sku": "JANUS.DATASET_SCOUT",
        "buyer_actor_id": buyer,
        "query": query,
        "domain": domain,
        "date_range": request.get("date_range"),
        "license_preferences": license_preferences,
        "format_preferences": format_preferences,
        "bounds": bounds,
        "read_only": True,
        "dataset_payload_download_authorized": False,
        "redistribution_authority_granted": False,
        "command_authority_granted": False,
        "external_effect_authorized": False,
    }
    service_request["request_hash"] = digest(service_request)
    purchase_id = "pur-ds-shadow-" + digest({
        "request_hash": service_request["request_hash"],
        "buyer_actor_id": buyer,
        "mode": "ZERO_PRICE_SHADOW",
    })[:32]
    grant = {
        "schema": "janus.machine_market.purchase_grant.v1",
        "purchase_id": purchase_id,
        "sku": "JANUS.DATASET_SCOUT",
        "status": "PURCHASE_ELIGIBLE",
        "execution_authority_granted": False,
        "service_entitlement": {
            "service": "JANUS.DATASET_SCOUT",
            "request_id": request_id,
            "bounds": bounds,
            "read_only": True,
            "dataset_payload_download_authorized": False,
            "redistribution_authority_granted": False,
        },
        "reasons": ["ZERO_PRICE_SHADOW_SERVICE_TEST", "PAYMENT_NOT_REQUIRED", "HOME_ADMISSION_REQUIRED"],
    }
    grant_hash = digest(grant)
    packet: dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "packet_id": "dsp-shadow-" + digest({"purchase_id": purchase_id, "request_hash": service_request["request_hash"]})[:48],
        "created_at": created_at,
        "sku": "JANUS.DATASET_SCOUT",
        "market_repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
        "home_repository": "Hawkar-usls/Hawkar-usls",
        "commerce_mode": "ZERO_PRICE_SHADOW",
        "money_enabled": False,
        "payment_reference": None,
        "purchase_grant": grant,
        "purchase_grant_hash": grant_hash,
        "service_request": service_request,
        "service_request_hash": service_request["request_hash"],
        "return_route": {
            "repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
            "source_issue_number": source_issue_number,
            "source_issue_id": source_issue_id,
        },
        "command_authority_granted": False,
        "external_effect_authorized": False,
        "dataset_payload_download_authorized": False,
        "redistribution_authority_granted": False,
    }
    packet["packet_hash"] = digest(packet)
    return packet


def verify_shadow_packet(packet: Mapping[str, Any]) -> bool:
    try:
        value = dict(packet)
        claimed = str(value.pop("packet_hash", ""))
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
        request = value.get("service_request") or {}
        rc = dict(request); request_hash = str(rc.pop("request_hash", ""))
        if len(request_hash) != 64 or digest(rc) != request_hash or value.get("service_request_hash") != request_hash:
            return False
        if request.get("schema") != REQUEST_SCHEMA or request.get("sku") != "JANUS.DATASET_SCOUT":
            return False
        if not str(request.get("query") or "").strip() or request.get("read_only") is not True:
            return False
        for key in ("dataset_payload_download_authorized", "redistribution_authority_granted", "command_authority_granted", "external_effect_authorized"):
            if request.get(key) is not False:
                return False
        grant = value.get("purchase_grant") or {}
        if digest(grant) != value.get("purchase_grant_hash") or grant.get("execution_authority_granted") is not False:
            return False
        ent = grant.get("service_entitlement") or {}
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    packet = build_shadow_packet(request)
    require(verify_shadow_packet(packet), "DATASET_SCOUT_PACKET_SELF_VERIFY_FAILED")
    Path(args.output).write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("DATASET_SCOUT_MARKET_PACKET=PASS")
    print("REQUEST_ID=" + packet["service_request"]["request_id"])
    print("PURCHASE_ID=" + packet["purchase_grant"]["purchase_id"])
    print("PACKET_HASH=" + packet["packet_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
