#!/usr/bin/env python3
"""JANUS MACHINE MARKET R1 zero-price shadow search engine.

This engine proves the commercial/idempotency contour without money and without
claiming production Activator authority. It searches only the checked-out market
catalog/product contracts, persists purchase/execution identity in SQLite, and
returns the exact same result/receipt for an exact retry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_REQUEST = "janus.machine_market.request.v1"
SCHEMA_QUOTE = "janus.machine_market.quote.v1"
SCHEMA_GRANT = "janus.machine_market.purchase_grant.v1"
SCHEMA_RECEIPT = "janus.machine_market.result_receipt.v1"
SKU = "JANUS.SEARCH"
ENGINE = "R1_SHADOW_MARKET_CATALOG_SEARCH"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def normalized_request(request: dict[str, Any]) -> dict[str, Any]:
    require(request.get("schema") == SCHEMA_REQUEST, "REQUEST_SCHEMA_INVALID")
    require(isinstance(request.get("request_id"), str) and request["request_id"].strip(), "REQUEST_ID_REQUIRED")
    require(request.get("sku") == SKU, "R1_ONLY_JANUS_SEARCH_ALLOWED")
    payload = request.get("input")
    require(isinstance(payload, dict), "REQUEST_INPUT_OBJECT_REQUIRED")
    query = payload.get("query")
    require(isinstance(query, str) and 1 <= len(query.strip()) <= 4000, "QUERY_INVALID")
    scope = payload.get("source_scope", "MARKET_CATALOG")
    require(scope == "MARKET_CATALOG", "R1_SOURCE_SCOPE_NOT_ALLOWED")
    max_results = payload.get("max_results", 5)
    require(isinstance(max_results, int) and 1 <= max_results <= 10, "MAX_RESULTS_OUT_OF_RANGE")
    max_runtime = request.get("max_runtime_seconds")
    if max_runtime is not None:
        require(isinstance(max_runtime, int) and 1 <= max_runtime <= 30, "MAX_RUNTIME_OUT_OF_RANGE")
    return {
        "schema": SCHEMA_REQUEST,
        "sku": SKU,
        "input": {
            "query": query.strip(),
            "source_scope": scope,
            "max_results": max_results,
        },
        "requested_output": request.get("requested_output"),
        "max_runtime_seconds": max_runtime,
    }


def tokenize(text: str) -> list[str]:
    return sorted({t for t in re.findall(r"[a-z0-9_.+-]+", text.lower()) if len(t) >= 2})


def load_catalog(catalog_path: Path, products_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    require(isinstance(catalog.get("products"), list), "CATALOG_PRODUCTS_INVALID")
    products: list[dict[str, Any]] = []
    for entry in catalog["products"]:
        rel = entry.get("product")
        if not isinstance(rel, str):
            continue
        path = products_dir.parent / rel
        if not path.is_file():
            continue
        product = json.loads(path.read_text(encoding="utf-8"))
        products.append({"catalog_entry": entry, "product": product, "path": rel, "sha256": digest(product)})
    return catalog, products


def bounded_search(query: str, max_results: int, catalog_path: Path, products_dir: Path) -> dict[str, Any]:
    catalog, products = load_catalog(catalog_path, products_dir)
    terms = tokenize(query)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for item in products:
        product = item["product"]
        entry = item["catalog_entry"]
        haystack = canonical({
            "sku": entry.get("sku"),
            "title": entry.get("title"),
            "class": entry.get("class"),
            "status": entry.get("status"),
            "product": product,
        }).lower()
        score = sum(1 for term in terms if term in haystack)
        if score > 0:
            scored.append((score, str(entry.get("sku", "")), item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    matches = []
    for score, _, item in scored[:max_results]:
        entry = item["catalog_entry"]
        product = item["product"]
        matches.append({
            "sku": entry.get("sku"),
            "title": entry.get("title"),
            "class": entry.get("class"),
            "status": entry.get("status"),
            "score": score,
            "summary": product.get("summary"),
            "product_contract": item["path"],
            "product_sha256": item["sha256"],
        })
    return {
        "schema": "janus.machine_market.shadow_search_result.v1",
        "engine": ENGINE,
        "query": query,
        "source_scope": "MARKET_CATALOG",
        "terms": terms,
        "match_count": len(matches),
        "matches": matches,
        "provenance": {
            "catalog": str(catalog_path),
            "catalog_sha256": digest(catalog),
            "network_access_used": False,
            "external_effects": False,
        },
    }


def connect_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS purchases (
          purchase_id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          quote_json TEXT NOT NULL,
          grant_json TEXT NOT NULL,
          purchase_grant_hash TEXT NOT NULL,
          execution_id TEXT NOT NULL UNIQUE,
          result_json TEXT NOT NULL,
          result_hash TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS executions (
          execution_id TEXT PRIMARY KEY,
          purchase_id TEXT NOT NULL UNIQUE,
          request_hash TEXT NOT NULL,
          result_hash TEXT NOT NULL
        );
        """
    )
    return db


def run(request: dict[str, Any], state_path: Path, catalog_path: Path, products_dir: Path) -> dict[str, Any]:
    norm = normalized_request(request)
    request_hash = digest(norm)
    offer = {
        "schema": "janus.machine_market.shadow_offer.v1",
        "sku": SKU,
        "mode": "ZERO_PRICE_SHADOW",
        "price": {"amount": "0", "asset": "NONE"},
        "payment_required": False,
        "production_purchase": False,
    }
    offer_hash = digest(offer)
    request_id = request["request_id"].strip()
    purchase_id = request.get("purchase_id") or f"pur-shadow-{digest({'request_id': request_id, 'request_hash': request_hash, 'offer_hash': offer_hash})[:32]}"
    quote = {
        "schema": SCHEMA_QUOTE,
        "quote_id": f"quo-shadow-{digest({'purchase_id': purchase_id, 'request_hash': request_hash})[:24]}",
        "request_id": request_id,
        "sku": SKU,
        "status": "QUOTED",
        "price": {"amount": "0", "asset": "NONE", "mode": "ZERO_PRICE_SHADOW"},
        "offer_hash": offer_hash,
        "request_hash": request_hash,
        "terms_hash": None,
        "expires_at": None,
        "payment_challenge": None,
        "reasons": ["R1_ZERO_PRICE_SHADOW_NO_PAYMENT"],
    }
    grant = {
        "schema": SCHEMA_GRANT,
        "purchase_id": purchase_id,
        "sku": SKU,
        "offer_hash": offer_hash,
        "request_hash": request_hash,
        "terms_hash": None,
        "payment_reference": None,
        "status": "PURCHASE_ELIGIBLE",
        "execution_authority_granted": False,
        "allowed_operation": "REQUEST_BOUNDED_SHADOW_SEARCH_EXECUTION",
        "authority_ceiling": {
            "sku": SKU,
            "source_scope": "MARKET_CATALOG",
            "network_access": False,
            "external_effects": False,
            "production_activator_authority": False,
        },
        "expires_at": None,
        "reasons": ["ZERO_PRICE_SHADOW_PURCHASE_GRANT_IS_NOT_EXECUTION_AUTHORITY"],
    }
    purchase_grant_hash = digest(grant)
    execution_id = f"exe-shadow-{digest({'purchase_id': purchase_id, 'request_hash': request_hash, 'engine': ENGINE})[:32]}"

    db = connect_state(state_path)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT request_hash, quote_json, grant_json, purchase_grant_hash, execution_id, result_json, result_hash, receipt_json FROM purchases WHERE purchase_id=?",
            (purchase_id,),
        ).fetchone()
        if row is not None:
            require(row[0] == request_hash, "IDEMPOTENCY_KEY_CONFLICT_PURCHASE_ID_BOUND_TO_DIFFERENT_REQUEST")
            db.commit()
            return {
                "schema": "janus.machine_market.shadow_roundtrip.v1",
                "replayed": True,
                "billable_execution_delta": 0,
                "execution_count_for_purchase": 1,
                "request_hash": request_hash,
                "quote": json.loads(row[1]),
                "purchase_grant": json.loads(row[2]),
                "purchase_grant_hash": row[3],
                "execution_id": row[4],
                "result": json.loads(row[5]),
                "result_sha256": row[6],
                "result_receipt": json.loads(row[7]),
            }

        result = bounded_search(norm["input"]["query"], norm["input"]["max_results"], catalog_path, products_dir)
        result_hash = digest(result)
        shadow_execution_receipt = {
            "schema": "janus.machine_market.shadow_execution_receipt.v1",
            "execution_id": execution_id,
            "authority_class": "R1_SHADOW_LOCAL_NON_EXTERNAL_EFFECT",
            "production_activator_authority": False,
            "request_hash": request_hash,
            "result_sha256": result_hash,
            "network_access_used": False,
            "external_effects": False,
        }
        receipt = {
            "schema": SCHEMA_RECEIPT,
            "purchase_id": purchase_id,
            "sku": SKU,
            "payment_reference": None,
            "purchase_grant_hash": purchase_grant_hash,
            "execution_grant_hash": None,
            "request_sha256": request_hash,
            "result_sha256": result_hash,
            "status": "DELIVERED",
            "organ": "JANUS_MACHINE_MARKET_R1_SHADOW_SEARCH",
            "runtime": {"engine": ENGINE, "mode": "ZERO_PRICE_SHADOW"},
            "resource_usage": {"network_requests": 0, "max_results": norm["input"]["max_results"]},
            "price": {"amount": "0", "asset": "NONE"},
            "settlement_reference": None,
            "result_reference": None,
            "inline_result": result,
            "execution_receipt": shadow_execution_receipt,
        }
        db.execute(
            "INSERT INTO purchases VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                purchase_id,
                request_id,
                request_hash,
                canonical(quote),
                canonical(grant),
                purchase_grant_hash,
                execution_id,
                canonical(result),
                result_hash,
                canonical(receipt),
            ),
        )
        db.execute(
            "INSERT INTO executions VALUES (?,?,?,?)",
            (execution_id, purchase_id, request_hash, result_hash),
        )
        db.commit()
        return {
            "schema": "janus.machine_market.shadow_roundtrip.v1",
            "replayed": False,
            "billable_execution_delta": 1,
            "execution_count_for_purchase": 1,
            "request_hash": request_hash,
            "quote": quote,
            "purchase_grant": grant,
            "purchase_grant_hash": purchase_grant_hash,
            "execution_id": execution_id,
            "result": result,
            "result_sha256": result_hash,
            "result_receipt": receipt,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS MACHINE MARKET R1 zero-price shadow search")
    parser.add_argument("--request", required=True)
    parser.add_argument("--state", default="state/r1-shadow-market.sqlite3")
    parser.add_argument("--catalog", default="CATALOG.json")
    parser.add_argument("--products-dir", default="products")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    envelope = run(request, Path(args.state), Path(args.catalog), Path(args.products_dir))
    text = json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
