#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build(*, catalog: dict[str, Any], price_decisions: list[dict[str, Any]], benchmarks: dict[str, Any], generated_at: str, catalog_commit: str) -> dict[str, Any]:
    prices = {row["sku"]: row for row in price_decisions if row.get("publishable") is True and row.get("candidate_price_atomic") is not None}
    available = []
    closed = []
    featured = []
    for product in catalog.get("products") or []:
        sku = product.get("sku")
        if product.get("machine_purchase") is True:
            available.append(sku)
        else:
            closed.append(sku)
        decision = prices.get(sku)
        if decision and float(decision.get("promotion_score", 0)) > 0 and product.get("machine_purchase") is True:
            featured.append({"sku": sku, "promotion_score": decision["promotion_score"]})
    featured.sort(key=lambda x: (-float(x["promotion_score"]), str(x["sku"])))
    as_of = benchmarks.get("as_of")
    now = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    bdt = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")).astimezone(timezone.utc)
    age_hours = max(0.0, (now - bdt).total_seconds() / 3600.0)
    return {
        "schema": "janus.machine_market.live_beacon.v1",
        "generated_at": generated_at,
        "catalog_commit": catalog_commit,
        "available_skus": available,
        "closed_skus": closed,
        "current_prices": {
            sku: {
                "amount_atomic": row["candidate_price_atomic"],
                "amount_usdt": row["candidate_price_usdt"],
                "competitive_ceiling_atomic": row["competitive_ceiling_atomic"]
            }
            for sku, row in sorted(prices.items())
        },
        "market_benchmark_freshness": {
            "as_of": as_of,
            "age_hours": round(age_hours, 6),
            "fresh_for_raise": age_hours <= 72
        },
        "featured_underused_services": featured[:5],
        "quote_protocol": "PURCHASE_PROTOCOL.json",
        "payment_route_status": "CLOSED_UNTIL_PRICE_AND_PAID_PR_CANONICAL",
        "open_fulfillment_debt_count": None,
        "service_health": "CONTRACT_ONLY_UNTIL_STATE_BRANCH_PROJECTION",
        "last_successful_roundtrip": {
            "sku": "JANUS.SEARCH",
            "mode": "ZERO_PRICE_OWNER_SHADOW",
            "status": "PROVEN"
        },
        "foreign_agent_witness_status": "PENDING",
        "authority": {
            "beacon_is_purchase_authority": False,
            "beacon_is_execution_authority": False
        }
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--catalog',default='CATALOG.json')
    parser.add_argument('--benchmarks',default='pricing/MARKET_BENCHMARKS.json')
    parser.add_argument('--decisions',required=True)
    parser.add_argument('--generated-at',required=True)
    parser.add_argument('--catalog-commit',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    catalog=json.loads(Path(args.catalog).read_text(encoding='utf-8'))
    benchmarks=json.loads(Path(args.benchmarks).read_text(encoding='utf-8'))
    decisions=json.loads(Path(args.decisions).read_text(encoding='utf-8'))
    value=build(catalog=catalog,price_decisions=decisions,benchmarks=benchmarks,generated_at=args.generated_at,catalog_commit=args.catalog_commit)
    Path(args.output).write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
