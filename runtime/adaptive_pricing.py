#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AdaptivePricingError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AdaptivePricingError(code)


def parse_time(value: str) -> datetime:
    text = str(value or "").strip()
    require(bool(text), "PRICING_TIMESTAMP_REQUIRED")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception as exc:  # noqa: BLE001
        raise AdaptivePricingError("PRICING_TIMESTAMP_INVALID") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class DemandSnapshot:
    sku: str
    successful_orders: int
    failed_orders: int
    open_fulfillment_debt: int
    hours_since_last_order: float | None

    @property
    def total_finished(self) -> int:
        return self.successful_orders + self.failed_orders

    @property
    def failure_rate(self) -> float:
        if self.total_finished <= 0:
            return 0.0
        return self.failed_orders / self.total_finished


def demand_multiplier(orders: int, target: int, policy: dict[str, Any]) -> float:
    require(target > 0, "DEMAND_TARGET_INVALID")
    d = policy["demand_response"]
    if orders <= 0:
        return float(d["zero_orders_multiplier"])
    ratio = orders / target
    if ratio < 0.25:
        return float(d["below_25_percent_target_multiplier"])
    if ratio < 1.0:
        return float(d["below_target_multiplier"])
    if ratio <= 1.5:
        return float(d["at_target_multiplier"])
    if ratio <= 3.0:
        return float(d["above_150_percent_target_multiplier"])
    return float(d["above_300_percent_target_multiplier"])


def promotion_score(snapshot: DemandSnapshot, *, target: int) -> float:
    demand_ratio = min(snapshot.successful_orders / max(target, 1), 4.0)
    inverse_demand = max(0.0, 1.0 - min(demand_ratio, 1.0))
    dormancy = 0.0 if snapshot.hours_since_last_order is None else min(snapshot.hours_since_last_order / 168.0, 2.0)
    debt_penalty = min(snapshot.open_fulfillment_debt / 10.0, 1.0)
    failure_penalty = min(snapshot.failure_rate * 4.0, 1.0)
    score = 0.65 * inverse_demand + 0.35 * dormancy - 0.55 * debt_penalty - 0.55 * failure_penalty
    return round(max(0.0, min(score, 1.0)), 6)


def comparable_market_ceiling_atomic(benchmarks: dict[str, Any], *, sku: str, fraction: float) -> int | None:
    rows = []
    for row in benchmarks.get("comparables") or []:
        if sku not in (row.get("comparable_to") or []):
            continue
        price = row.get("usd_per_unit")
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            continue
        rows.append(float(price))
    if not rows:
        return None
    atomic = math.floor(min(rows) * fraction * 1_000_000)
    return max(1, atomic)


def rebalance(
    *,
    policy: dict[str, Any],
    benchmarks: dict[str, Any],
    sku: str,
    current_price_atomic: int | None,
    floor_atomic: int,
    snapshot: DemandSnapshot,
    now: datetime,
) -> dict[str, Any]:
    require(policy.get("schema") == "janus.machine_market.adaptive_pricing_policy.v1", "ADAPTIVE_POLICY_SCHEMA_INVALID")
    require(benchmarks.get("schema") == "janus.machine_market.market_benchmarks.v1", "MARKET_BENCHMARK_SCHEMA_INVALID")
    require(floor_atomic >= 0, "PRICE_FLOOR_INVALID")
    if current_price_atomic is not None:
        require(isinstance(current_price_atomic, int) and not isinstance(current_price_atomic, bool) and current_price_atomic > 0, "CURRENT_PRICE_INVALID")

    rules = policy["rules"]
    fraction = float(rules["competitive_ceiling_fraction_of_lowest_comparable_market_price"])
    require(0 < fraction < 1, "COMPETITIVE_CEILING_FRACTION_INVALID")
    market_ceiling = comparable_market_ceiling_atomic(benchmarks, sku=sku, fraction=fraction)
    require(market_ceiling is not None, "NO_COMPARABLE_MARKET_BENCHMARK")

    as_of = parse_time(benchmarks["as_of"])
    age_hours = max(0.0, (now.astimezone(timezone.utc) - as_of).total_seconds() / 3600.0)
    fresh = age_hours <= float(rules["market_benchmark_max_age_hours"])

    target_orders = int(rules["demand_target_orders_per_window"])
    multiplier = demand_multiplier(snapshot.successful_orders, target_orders, policy)
    suggested_seed = ((benchmarks.get("derived") or {}).get(sku) or {}).get("suggested_shadow_price_usdt_atomic")
    if current_price_atomic is None:
        require(isinstance(suggested_seed, int) and suggested_seed > 0, "PRICE_SEED_MISSING")
        base = suggested_seed
    else:
        base = current_price_atomic

    desired = max(floor_atomic, int(round(base * multiplier)))
    raise_frozen_reasons: list[str] = []
    if not fresh:
        raise_frozen_reasons.append("MARKET_BENCHMARK_STALE")
    if snapshot.failure_rate > float(rules["failure_rate_raise_freeze_threshold"]):
        raise_frozen_reasons.append("SERVICE_FAILURE_RATE_TOO_HIGH")
    if bool(rules["open_fulfillment_debt_raise_freeze"]) and snapshot.open_fulfillment_debt > 0:
        raise_frozen_reasons.append("OPEN_FULFILLMENT_DEBT")

    if current_price_atomic is not None:
        max_up = max(current_price_atomic, math.floor(current_price_atomic * (1.0 + float(rules["max_raise_fraction_per_rebalance"]))))
        max_down = max(floor_atomic, math.ceil(current_price_atomic * (1.0 - float(rules["max_drop_fraction_per_rebalance"]))))
        desired = min(desired, max_up)
        desired = max(desired, max_down)
        if raise_frozen_reasons and desired > current_price_atomic:
            desired = current_price_atomic

    desired = min(desired, market_ceiling)
    if floor_atomic > market_ceiling:
        return {
            "schema": "janus.machine_market.adaptive_price_decision.v1",
            "sku": sku,
            "status": "HOLD_COST_FLOOR_ABOVE_COMPETITIVE_CEILING",
            "publishable": False,
            "current_price_atomic": current_price_atomic,
            "candidate_price_atomic": None,
            "floor_atomic": floor_atomic,
            "competitive_ceiling_atomic": market_ceiling,
            "market_benchmark_age_hours": round(age_hours, 6),
            "market_benchmark_fresh": fresh,
            "demand_multiplier": multiplier,
            "promotion_score": promotion_score(snapshot, target=target_orders),
            "raise_frozen_reasons": raise_frozen_reasons,
        }

    status = "PRICE_DECREASE" if current_price_atomic and desired < current_price_atomic else (
        "PRICE_INCREASE" if current_price_atomic and desired > current_price_atomic else (
            "PRICE_HOLD" if current_price_atomic else "PRICE_SEED_CANDIDATE"
        )
    )
    return {
        "schema": "janus.machine_market.adaptive_price_decision.v1",
        "sku": sku,
        "status": status,
        "publishable": True,
        "current_price_atomic": current_price_atomic,
        "candidate_price_atomic": desired,
        "candidate_price_usdt": f"{desired / 1_000_000:.6f}",
        "floor_atomic": floor_atomic,
        "competitive_ceiling_atomic": market_ceiling,
        "market_benchmark_age_hours": round(age_hours, 6),
        "market_benchmark_fresh": fresh,
        "demand_successful_orders": snapshot.successful_orders,
        "demand_failed_orders": snapshot.failed_orders,
        "open_fulfillment_debt": snapshot.open_fulfillment_debt,
        "failure_rate": round(snapshot.failure_rate, 6),
        "demand_multiplier": multiplier,
        "promotion_score": promotion_score(snapshot, target=target_orders),
        "raise_frozen_reasons": raise_frozen_reasons,
        "existing_quotes_affected": False,
        "execution_authority_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute one fail-closed JANUS adaptive price decision")
    parser.add_argument("--policy", default="ADAPTIVE_PRICING_POLICY.json")
    parser.add_argument("--benchmarks", default="pricing/MARKET_BENCHMARKS.json")
    parser.add_argument("--sku", required=True)
    parser.add_argument("--current-price-atomic", type=int)
    parser.add_argument("--floor-atomic", type=int, default=0)
    parser.add_argument("--successful-orders", type=int, default=0)
    parser.add_argument("--failed-orders", type=int, default=0)
    parser.add_argument("--open-fulfillment-debt", type=int, default=0)
    parser.add_argument("--hours-since-last-order", type=float)
    parser.add_argument("--now", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    benchmarks = json.loads(Path(args.benchmarks).read_text(encoding="utf-8"))
    snapshot = DemandSnapshot(
        sku=args.sku,
        successful_orders=max(0, args.successful_orders),
        failed_orders=max(0, args.failed_orders),
        open_fulfillment_debt=max(0, args.open_fulfillment_debt),
        hours_since_last_order=args.hours_since_last_order,
    )
    decision = rebalance(
        policy=policy,
        benchmarks=benchmarks,
        sku=args.sku,
        current_price_atomic=args.current_price_atomic,
        floor_atomic=args.floor_atomic,
        snapshot=snapshot,
        now=parse_time(args.now),
    )
    Path(args.output).write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
