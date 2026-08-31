from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from runtime.adaptive_pricing import DemandSnapshot, rebalance

ROOT = Path(__file__).resolve().parents[1]


class AdaptivePricingTest(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / "ADAPTIVE_PRICING_POLICY.json").read_text(encoding="utf-8"))
        self.bench = json.loads((ROOT / "pricing/MARKET_BENCHMARKS.json").read_text(encoding="utf-8"))
        self.now = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)

    def decision(self, *, current=5900, orders=0, failed=0, debt=0, hours=168, floor=1000, now=None):
        return rebalance(
            policy=self.policy,
            benchmarks=self.bench,
            sku="JANUS.SEARCH",
            current_price_atomic=current,
            floor_atomic=floor,
            snapshot=DemandSnapshot(
                sku="JANUS.SEARCH",
                successful_orders=orders,
                failed_orders=failed,
                open_fulfillment_debt=debt,
                hours_since_last_order=hours,
            ),
            now=now or self.now,
        )

    def test_underused_service_gets_cheaper_and_more_promotion(self):
        d = self.decision(current=5900, orders=0, hours=240)
        self.assertEqual(d["status"], "PRICE_DECREASE")
        self.assertLess(d["candidate_price_atomic"], 5900)
        self.assertGreater(d["promotion_score"], 0.5)

    def test_high_demand_can_rise_but_never_above_market_ceiling(self):
        d = self.decision(current=5600, orders=400, hours=1)
        self.assertEqual(d["status"], "PRICE_INCREASE")
        self.assertGreater(d["candidate_price_atomic"], 5600)
        self.assertLessEqual(d["candidate_price_atomic"], d["competitive_ceiling_atomic"])
        self.assertEqual(d["competitive_ceiling_atomic"], 5950)

    def test_existing_quote_never_changes(self):
        d = self.decision(current=5600, orders=400)
        self.assertFalse(d["existing_quotes_affected"])
        self.assertFalse(d["execution_authority_granted"])

    def test_stale_market_data_freezes_raises(self):
        stale_now = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
        d = self.decision(current=5600, orders=400, now=stale_now)
        self.assertEqual(d["candidate_price_atomic"], 5600)
        self.assertIn("MARKET_BENCHMARK_STALE", d["raise_frozen_reasons"])

    def test_open_service_debt_freezes_raise(self):
        d = self.decision(current=5600, orders=400, debt=1)
        self.assertEqual(d["candidate_price_atomic"], 5600)
        self.assertIn("OPEN_FULFILLMENT_DEBT", d["raise_frozen_reasons"])

    def test_failure_rate_freezes_raise(self):
        d = self.decision(current=5600, orders=400, failed=30)
        self.assertEqual(d["candidate_price_atomic"], 5600)
        self.assertIn("SERVICE_FAILURE_RATE_TOO_HIGH", d["raise_frozen_reasons"])

    def test_cost_floor_above_competitive_cap_holds_sale(self):
        d = self.decision(current=5900, orders=0, floor=6000)
        self.assertEqual(d["status"], "HOLD_COST_FLOOR_ABOVE_COMPETITIVE_CEILING")
        self.assertFalse(d["publishable"])
        self.assertIsNone(d["candidate_price_atomic"])

    def test_no_current_price_seeds_below_market(self):
        d = self.decision(current=None, orders=100)
        self.assertEqual(d["status"], "PRICE_SEED_CANDIDATE")
        self.assertEqual(d["candidate_price_atomic"], 5900)
        self.assertLess(d["candidate_price_atomic"], 7000)


if __name__ == "__main__":
    unittest.main()
