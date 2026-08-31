from datetime import datetime, timezone
from pathlib import Path

import pytest

from runtime.commerce_authority import USDT_ETHEREUM, admit_purchase, build_quote, digest
from runtime.commerce_search_executor import execute

RECEIVER = "0x7149081aea54fbef57effeb52a5a966b81cc03a0"
TX = "0x" + "ab" * 32
NOW = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)


def request(max_results=3, max_runtime=10):
    return {
        "schema": "janus.machine_market.request.v1",
        "request_id": "req-paid-search-1",
        "purchase_id": None,
        "sku": "JANUS.SEARCH",
        "input": {"query": "dataset research search", "source_scope": "MARKET_CATALOG", "max_results": max_results},
        "requested_output": {"format": "application/json"},
        "max_runtime_seconds": max_runtime,
        "created_at": None,
    }


def quote(req):
    return build_quote(request=req, sku="JANUS.SEARCH", amount_usdt_micros=50_000, receiving_address=RECEIVER, expires_at="2026-08-31T19:00:00+00:00", nonce="search-paid", policy_version="v1")


def payment(req):
    q = quote(req)
    return {
        "schema": "janus.machine_market.payment_receipt.v1", "status": "CONFIRMED", "quote_hash": q["quote_hash"],
        "tx_hash": TX, "log_index": 2, "payment_reference": f"{TX}:2", "chain_id": 1,
        "token_contract": USDT_ETHEREUM, "to": RECEIVER, "amount_usdt_micros": 50_000,
        "confirmations": 12, "required_confirmations": 12,
    }


def purchase(req):
    return admit_purchase(
        readiness={"money_enabled": True, "autonomous_purchase_declared": True},
        foreign_witness={"foreign_agent_witness": True},
        product={"sku": "JANUS.SEARCH", "machine_purchase": True},
        request=req, quote=quote(req), payment_receipt=payment(req), now=NOW,
    )


def execution_grant(req, pur, *, max_results=10, max_runtime=30, expires="2026-08-31T19:00:00+00:00"):
    body = {
        "schema": "janus.machine_market.execution_grant.v1",
        "grant_id": "eg-paid-search-0001",
        "purchase_id": pur["purchase_id"],
        "purchase_grant_hash": pur["grant_hash"],
        "sku": "JANUS.SEARCH",
        "request_hash": pur["request_hash"],
        "status": "EXECUTION_GRANTED",
        "allowed_operation": "JANUS.SEARCH.MARKET_CATALOG",
        "authority": {
            "source_scope": "MARKET_CATALOG", "max_results": max_results,
            "max_runtime_seconds": max_runtime, "network_access": False,
            "external_effects": False, "target_execution_performed": False,
        },
        "expires_at": expires,
        "issued_by": "JANUS_ACTIVATOR_TEST",
    }
    return {**body, "grant_hash": digest(body)}


def test_valid_execution_grant_delivers_bounded_search_receipt():
    req = request(); pur = purchase(req); eg = execution_grant(req, pur)
    out = execute(request=req, purchase_grant=pur, execution_grant=eg, catalog_path=Path("CATALOG.json"), products_dir=Path("products"), now=NOW)
    assert out["status"] == "DELIVERED"
    assert out["payment_reference"] == f"{TX}:2"
    assert out["execution_receipt"]["network_access_used"] is False
    assert out["execution_receipt"]["external_effects"] is False
    assert out["inline_result"]["provenance"]["network_access_used"] is False


def test_purchase_grant_alone_cannot_execute():
    req = request(); pur = purchase(req); eg = execution_grant(req, pur)
    eg["status"] = "DENIED"
    with pytest.raises(ValueError, match="execution not granted"):
        execute(request=req, purchase_grant=pur, execution_grant=eg, catalog_path=Path("CATALOG.json"), products_dir=Path("products"), now=NOW)


def test_tampered_execution_grant_hash_is_rejected():
    req = request(); pur = purchase(req); eg = execution_grant(req, pur)
    eg["authority"]["external_effects"] = True
    with pytest.raises(ValueError, match="execution grant hash invalid"):
        execute(request=req, purchase_grant=pur, execution_grant=eg, catalog_path=Path("CATALOG.json"), products_dir=Path("products"), now=NOW)


def test_validly_hashed_grant_still_cannot_authorize_external_effects():
    req = request(); pur = purchase(req); eg = execution_grant(req, pur)
    eg["authority"]["external_effects"] = True
    body = dict(eg); body.pop("grant_hash")
    eg["grant_hash"] = digest(body)
    with pytest.raises(ValueError, match="external authority denied"):
        execute(request=req, purchase_grant=pur, execution_grant=eg, catalog_path=Path("CATALOG.json"), products_dir=Path("products"), now=NOW)


def test_request_cannot_exceed_execution_result_cap():
    req = request(max_results=5); pur = purchase(req); eg = execution_grant(req, pur, max_results=3)
    with pytest.raises(ValueError, match="exceeds granted result cap"):
        execute(request=req, purchase_grant=pur, execution_grant=eg, catalog_path=Path("CATALOG.json"), products_dir=Path("products"), now=NOW)


def test_expired_execution_grant_is_rejected():
    req = request(); pur = purchase(req); eg = execution_grant(req, pur, expires="2026-08-31T17:59:59+00:00")
    with pytest.raises(ValueError, match="execution grant expired"):
        execute(request=req, purchase_grant=pur, execution_grant=eg, catalog_path=Path("CATALOG.json"), products_dir=Path("products"), now=NOW)
