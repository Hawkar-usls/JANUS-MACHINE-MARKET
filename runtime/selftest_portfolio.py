#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXCLUDED = {"HELIOS.PILOT"}
LIVE_RESULT_REQUIRED = {"JANUS.SEARCH"}
CLOSED_EXPECTED = {"JANUS.INFERENCE", "JANUS.COMPUTE"}


def classify_product(product: dict[str, Any]) -> dict[str, Any]:
    sku = str(product.get("sku") or "")
    status = str(product.get("status") or "")
    if sku in EXCLUDED:
        return {"sku": sku, "test_action": "EXCLUDED_BY_USER", "expected": "NOT_TOUCHED"}
    if sku in CLOSED_EXPECTED or status.startswith("CLOSED_"):
        return {"sku": sku, "test_action": "ATTEMPT_ADMISSION", "expected": "FAIL_CLOSED_NOT_PURCHASABLE"}
    if sku in LIVE_RESULT_REQUIRED:
        return {"sku": sku, "test_action": "LIVE_OWNER_SHADOW_ROUNDTRIP", "expected": "VERIFIED_RESULT_RECEIPT_REQUIRED"}
    return {"sku": sku, "test_action": "ATTEMPT_ADMISSION", "expected": "BLOCK_SPECIFICATION_ONLY_NOT_YET_LIVE"}


def build_matrix(products_dir: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(products_dir.glob("*.json")):
        product = json.loads(path.read_text(encoding="utf-8"))
        rows.append(classify_product(product))
    return {
        "schema": "janus.machine_market.self_test_portfolio_result.v1",
        "rows": rows,
        "laws": [
            "TEST CREDIT != MONEY",
            "SPECIFICATION READY != SERVICE DELIVERED",
            "CLOSED SKU MUST FAIL CLOSED",
            "HELIOS PILOT MUST NOT BE TOUCHED",
            "LIVE SERVICE REQUIRES REAL RESULT RECEIPT"
        ]
    }


if __name__ == "__main__":
    print(json.dumps(build_matrix(Path("products")), ensure_ascii=False, indent=2, sort_keys=True))
