#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REQUEST_SCHEMA = "janus.market_service.repo_audit_request.v1"
PACKET_SCHEMA = "janus.machine_market.home_repo_audit_packet.v1"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def normalize_repo(value: str) -> str:
    text = str(value or "").strip().strip("/")
    if text.startswith("https://github.com/"):
        text = text[len("https://github.com/"):].strip("/")
    if text.endswith(".git"):
        text = text[:-4]
    parts = text.split("/")
    require(len(parts) == 2 and all(re.fullmatch(r"[A-Za-z0-9_.-]+", x or "") for x in parts), "REPO_AUDIT_REPOSITORY_INVALID")
    return "/".join(parts)


def build_shadow_packet(request: dict[str, Any]) -> dict[str, Any]:
    buyer = str(request.get("buyer_actor_id") or "").strip()
    repository = normalize_repo(str(request.get("repository") or ""))
    ref = str(request.get("ref") or "main").strip()
    source_issue_id = request.get("source_issue_id")
    source_issue_number = request.get("source_issue_number")
    created_at = str(request.get("created_at") or "").strip()
    require(bool(buyer and ref and created_at), "REPO_AUDIT_PROVENANCE_REQUIRED")
    require(isinstance(source_issue_id, int) and not isinstance(source_issue_id, bool), "REPO_AUDIT_SOURCE_ISSUE_ID_REQUIRED")
    bounds = {
        "max_tree_entries": min(max(int(request.get("max_tree_entries", 5000)), 1), 10000),
        "max_blob_files": min(max(int(request.get("max_blob_files", 24)), 1), 40),
        "max_total_blob_bytes": min(max(int(request.get("max_total_blob_bytes", 750000)), 1), 2000000),
    }
    request_id = "ra-shadow-" + digest({
        "source_issue_id": source_issue_id,
        "buyer_actor_id": buyer,
        "repository": repository,
        "ref": ref,
        "bounds": bounds,
    })[:48]
    service_request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "sku": "JANUS.REPO_AUDIT",
        "buyer_actor_id": buyer,
        "repository": repository,
        "ref": ref,
        "audit_scope": "BOUNDED_STATIC_REPOSITORY_SURFACE",
        "bounds": bounds,
        "read_only": True,
        "execute_repository_code": False,
        "command_authority_granted": False,
        "external_effect_authorized": False,
    }
    service_request["request_hash"] = digest(service_request)
    purchase_id = "pur-ra-shadow-" + digest({
        "request_hash": service_request["request_hash"],
        "buyer_actor_id": buyer,
        "mode": "ZERO_PRICE_SHADOW",
    })[:32]
    grant = {
        "schema": "janus.machine_market.purchase_grant.v1",
        "purchase_id": purchase_id,
        "sku": "JANUS.REPO_AUDIT",
        "status": "PURCHASE_ELIGIBLE",
        "execution_authority_granted": False,
        "service_entitlement": {
            "service": "JANUS.REPO_AUDIT",
            "repository": repository,
            "ref": ref,
            "bounds": bounds,
            "read_only": True,
            "execute_repository_code": False,
        },
        "reasons": ["ZERO_PRICE_SHADOW_SERVICE_TEST", "PAYMENT_NOT_REQUIRED", "HOME_ADMISSION_REQUIRED"],
    }
    grant_hash = digest(grant)
    packet: dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "packet_id": "rap-shadow-" + digest({"purchase_id": purchase_id, "request_hash": service_request["request_hash"]})[:48],
        "created_at": created_at,
        "sku": "JANUS.REPO_AUDIT",
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
        "repository_write_authorized": False,
        "execute_repository_code": False,
    }
    packet["packet_hash"] = digest(packet)
    return packet


def verify_shadow_packet(packet: dict[str, Any]) -> bool:
    try:
        value = dict(packet)
        claimed = value.pop("packet_hash")
        if digest(value) != claimed or len(claimed) != 64:
            return False
        if value.get("schema") != PACKET_SCHEMA or value.get("sku") != "JANUS.REPO_AUDIT":
            return False
        if value.get("commerce_mode") != "ZERO_PRICE_SHADOW" or value.get("money_enabled") is not False or value.get("payment_reference") is not None:
            return False
        if value.get("market_repository") != "Hawkar-usls/JANUS-MACHINE-MARKET" or value.get("home_repository") != "Hawkar-usls/Hawkar-usls":
            return False
        if value.get("command_authority_granted") is not False or value.get("external_effect_authorized") is not False:
            return False
        if value.get("repository_write_authorized") is not False or value.get("execute_repository_code") is not False:
            return False
        sr = value["service_request"]
        sr_copy = dict(sr); sr_hash = sr_copy.pop("request_hash")
        if digest(sr_copy) != sr_hash or value.get("service_request_hash") != sr_hash:
            return False
        grant = value["purchase_grant"]
        if digest(grant) != value.get("purchase_grant_hash") or grant.get("execution_authority_granted") is not False:
            return False
        ent = grant.get("service_entitlement") or {}
        return all([
            ent.get("service") == "JANUS.REPO_AUDIT",
            ent.get("repository") == sr.get("repository"),
            ent.get("ref") == sr.get("ref"),
            ent.get("read_only") is True,
            ent.get("execute_repository_code") is False,
        ])
    except Exception:
        return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    req = json.loads(Path(a.request).read_text(encoding="utf-8"))
    packet = build_shadow_packet(req)
    require(verify_shadow_packet(packet), "REPO_AUDIT_PACKET_SELF_VERIFY_FAILED")
    Path(a.output).write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("REPO_AUDIT_MARKET_PACKET=PASS")
    print("REQUEST_ID=" + packet["service_request"]["request_id"])
    print("PURCHASE_ID=" + packet["purchase_grant"]["purchase_id"])
    print("PACKET_HASH=" + packet["packet_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
