"""Bounded JANUS.SEARCH executor for a settled commerce purchase.

The MARKET does not mint EXECUTION_GRANTs here. It consumes a separate grant
issued by the JANUS authority plane, verifies all bindings and ceilings, then
reuses the already-proven catalog search primitive. No network access or external
effects are permitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.commerce_authority import CommerceInvalid, digest, parse_time, request_hash
from runtime.r1_shadow_search import bounded_search, normalized_request

SKU = "JANUS.SEARCH"
OPERATION = "JANUS.SEARCH.MARKET_CATALOG"
ENGINE = "COMMERCE_BOUNDED_MARKET_CATALOG_SEARCH"


def _hash_without(value: dict[str, Any], field: str) -> str:
    body = dict(value); body.pop(field, None)
    return digest(body)


def validate_purchase_grant(grant: dict[str, Any], request: dict[str, Any]) -> None:
    if grant.get("schema") != "janus.machine_market.purchase_grant.v1": raise CommerceInvalid("purchase grant schema invalid")
    if grant.get("status") != "PURCHASE_SETTLED": raise CommerceInvalid("purchase not settled")
    if grant.get("sku") != SKU: raise CommerceInvalid("purchase SKU not supported")
    if grant.get("execution_authority_granted") is not False: raise CommerceInvalid("purchase grant cannot itself authorize execution")
    if grant.get("request_hash") != request_hash(request): raise CommerceInvalid("purchase/request hash mismatch")
    supplied = grant.get("grant_hash")
    if not supplied or supplied != _hash_without(grant, "grant_hash"): raise CommerceInvalid("purchase grant hash invalid")
    if not grant.get("payment_reference"): raise CommerceInvalid("settled purchase missing payment reference")


def validate_execution_grant(execution_grant: dict[str, Any], purchase_grant: dict[str, Any], request: dict[str, Any], *, now: datetime | None = None) -> None:
    if execution_grant.get("schema") != "janus.machine_market.execution_grant.v1": raise CommerceInvalid("execution grant schema invalid")
    if execution_grant.get("status") != "EXECUTION_GRANTED": raise CommerceInvalid("execution not granted")
    if execution_grant.get("sku") != SKU or execution_grant.get("allowed_operation") != OPERATION: raise CommerceInvalid("execution operation not allowed")
    if execution_grant.get("purchase_id") != purchase_grant.get("purchase_id"): raise CommerceInvalid("execution/purchase id mismatch")
    if execution_grant.get("purchase_grant_hash") != purchase_grant.get("grant_hash"): raise CommerceInvalid("execution/purchase grant hash mismatch")
    exact_request_hash = request_hash(request)
    if execution_grant.get("request_hash") != exact_request_hash: raise CommerceInvalid("execution/request hash mismatch")
    grant_hash = execution_grant.get("grant_hash")
    if not grant_hash or grant_hash != _hash_without(execution_grant, "grant_hash"): raise CommerceInvalid("execution grant hash invalid")
    if parse_time(execution_grant["expires_at"]) <= (now or datetime.now(timezone.utc)): raise CommerceInvalid("execution grant expired")
    authority = execution_grant.get("authority")
    if not isinstance(authority, dict): raise CommerceInvalid("execution authority object required")
    if authority.get("source_scope") != "MARKET_CATALOG": raise CommerceInvalid("execution source scope denied")
    if authority.get("network_access") is not False or authority.get("external_effects") is not False: raise CommerceInvalid("external authority denied")
    if authority.get("target_execution_performed") is not False: raise CommerceInvalid("grant must precede target execution")
    max_results = int(authority.get("max_results", 0)); max_runtime = int(authority.get("max_runtime_seconds", 0))
    if not 1 <= max_results <= 10 or not 1 <= max_runtime <= 30: raise CommerceInvalid("execution authority ceiling invalid")
    norm = normalized_request(request)
    if norm["input"]["max_results"] > max_results: raise CommerceInvalid("request exceeds granted result cap")
    requested_runtime = norm.get("max_runtime_seconds") or 30
    if requested_runtime > max_runtime: raise CommerceInvalid("request exceeds granted runtime cap")


def execute(
    *, request: dict[str, Any], purchase_grant: dict[str, Any], execution_grant: dict[str, Any],
    catalog_path: Path, products_dir: Path, now: datetime | None = None,
) -> dict[str, Any]:
    validate_purchase_grant(purchase_grant, request)
    validate_execution_grant(execution_grant, purchase_grant, request, now=now)
    norm = normalized_request(request)
    result = bounded_search(norm["input"]["query"], norm["input"]["max_results"], catalog_path, products_dir)
    result_hash = digest(result)
    execution_id = "exe-commerce-" + digest({
        "grant_id": execution_grant["grant_id"], "purchase_id": purchase_grant["purchase_id"],
        "request_hash": purchase_grant["request_hash"], "engine": ENGINE,
    })[:40]
    execution_receipt = {
        "schema": "janus.machine_market.execution_receipt.v1",
        "execution_id": execution_id,
        "grant_id": execution_grant["grant_id"],
        "purchase_id": purchase_grant["purchase_id"],
        "authority_class": "BOUNDED_COMMERCE_SEARCH",
        "request_hash": purchase_grant["request_hash"],
        "result_sha256": result_hash,
        "network_access_used": False,
        "external_effects": False,
    }
    return {
        "schema": "janus.machine_market.result_receipt.v1",
        "purchase_id": purchase_grant["purchase_id"],
        "sku": SKU,
        "payment_reference": purchase_grant["payment_reference"],
        "purchase_grant_hash": purchase_grant["grant_hash"],
        "execution_grant_hash": execution_grant["grant_hash"],
        "request_sha256": purchase_grant["request_hash"],
        "result_sha256": result_hash,
        "status": "DELIVERED",
        "organ": "JANUS_MACHINE_MARKET_COMMERCE_SEARCH",
        "runtime": {"engine": ENGINE, "mode": "BOUNDED_COMMERCE"},
        "resource_usage": {"network_requests": 0, "max_results": norm["input"]["max_results"]},
        "price": {"amount_usdt_micros": purchase_grant.get("amount_usdt_micros"), "asset": "USDT"},
        "settlement_reference": purchase_grant["payment_reference"],
        "result_reference": None,
        "inline_result": result,
        "execution_receipt": execution_receipt,
    }
