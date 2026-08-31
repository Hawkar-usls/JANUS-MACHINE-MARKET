from __future__ import annotations

import unittest

from runtime.live_beacon import build


class LiveBeaconTest(unittest.TestCase):
    def test_closed_products_are_not_featured(self):
        catalog={"products":[
            {"sku":"JANUS.SEARCH","machine_purchase":True},
            {"sku":"JANUS.COMPUTE","machine_purchase":False},
        ]}
        decisions=[
            {"sku":"JANUS.SEARCH","publishable":True,"candidate_price_atomic":5000,"candidate_price_usdt":"0.005000","competitive_ceiling_atomic":5950,"promotion_score":0.8},
            {"sku":"JANUS.COMPUTE","publishable":True,"candidate_price_atomic":1,"candidate_price_usdt":"0.000001","competitive_ceiling_atomic":100,"promotion_score":1.0},
        ]
        benchmarks={"as_of":"2026-08-31T07:19:00Z"}
        b=build(catalog=catalog,price_decisions=decisions,benchmarks=benchmarks,generated_at="2026-08-31T08:00:00Z",catalog_commit="a"*40)
        self.assertEqual(b["available_skus"],["JANUS.SEARCH"])
        self.assertIn("JANUS.COMPUTE",b["closed_skus"])
        self.assertEqual([x["sku"] for x in b["featured_underused_services"]],["JANUS.SEARCH"])
        self.assertFalse(b["authority"]["beacon_is_purchase_authority"])


if __name__=='__main__':
    unittest.main()
