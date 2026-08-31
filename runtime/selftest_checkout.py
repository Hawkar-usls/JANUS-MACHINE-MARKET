#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime.buyer_accounts import build_event, project
from runtime.selftest_portfolio import build_matrix

SELFTEST_COST = 100


def run_checkout(*, agent: dict[str, Any], products_dir: Path, verified_search_receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    actor = str(agent["agent_id"])
    credit = int(agent["initial_test_credit"])
    rows = build_matrix(products_dir)["rows"]
    events: list[dict[str, Any]] = []
    prev = None

    def emit(event_type: str, event_id: str, payload: dict[str, Any]) -> None:
        nonlocal prev
        event = build_event(
            buyer_actor_id=actor,
            event_type=event_type,
            event_id=event_id,
            created_at="2026-08-31T07:50:00Z",
            payload=payload,
            previous_event_hash=prev,
        )
        events.append(event)
        prev = event["event_hash"]

    emit("MARKET_TEST_CREDIT_MINTED", "portfolio-credit-v1", {
        "amount": credit,
        "asset": "MARKET_TEST_CREDIT",
        "cash_value": False,
    })

    results = []
    for row in rows:
        sku = row["sku"]
        action = row["test_action"]
        if action == "EXCLUDED_BY_USER":
            results.append({"sku": sku, "status": "EXCLUDED_BY_USER", "spent": 0})
            continue
        if action == "ATTEMPT_ADMISSION":
            expected = row["expected"]
            status = "BLOCKED_CLOSED" if expected == "FAIL_CLOSED_NOT_PURCHASABLE" else "BLOCKED_SPECIFICATION_ONLY"
            results.append({"sku": sku, "status": status, "spent": 0})
            continue

        # Only a service with a proven execution path is allowed to consume test credit.
        emit("MARKET_TEST_CREDIT_SPENT", f"portfolio-spend:{sku}:v1", {"amount": SELFTEST_COST, "sku": sku})
        emit("PURCHASE_ADMITTED", f"portfolio-purchase:{sku}:v1", {"sku": sku, "test_only": True})
        debt_id = f"selftest-debt:{sku}:v1"
        emit("SERVICE_DEBT_OPENED", f"portfolio-debt:{sku}:v1", {"service_debt_id": debt_id, "sku": sku})
        status = "ADMITTED_AWAITING_VERIFIED_RESULT"
        if verified_search_receipt is not None and sku == "JANUS.SEARCH":
            if verified_search_receipt.get("sku") != "JANUS.SEARCH" or verified_search_receipt.get("verified") is not True:
                raise ValueError("SELFTEST_SEARCH_RECEIPT_INVALID")
            emit("SERVICE_DELIVERED", f"portfolio-delivered:{sku}:v1", {
                "service_debt_id": debt_id,
                "sku": sku,
                "result_identity": verified_search_receipt.get("result_identity"),
                "receipt_hash": verified_search_receipt.get("receipt_hash"),
            })
            status = "FULFILLED_VERIFIED_RESULT"
        results.append({"sku": sku, "status": status, "spent": SELFTEST_COST})

    head = project(events)
    return {
        "schema": "janus.machine_market.self_test_checkout_result.v1",
        "agent_id": actor,
        "cash_value": False,
        "results": results,
        "account_head": head,
        "laws": [
            "TEST CREDIT != MONEY",
            "BLOCKED SKU MUST NOT CONSUME CREDIT",
            "SERVICE ADMISSION OPENS SERVICE DEBT",
            "SERVICE DEBT CLOSES ONLY ON VERIFIED RESULT",
            "HELIOS.PILOT IS EXCLUDED"
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default="SELF_TEST_AGENT.json")
    p.add_argument("--products", default="products")
    p.add_argument("--search-receipt")
    p.add_argument("--output", default="-")
    a = p.parse_args()
    agent = json.loads(Path(a.agent).read_text(encoding="utf-8"))
    receipt = json.loads(Path(a.search_receipt).read_text(encoding="utf-8")) if a.search_receipt else None
    result = run_checkout(agent=agent, products_dir=Path(a.products), verified_search_receipt=receipt)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if a.output == "-": print(text, end="")
    else: Path(a.output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
