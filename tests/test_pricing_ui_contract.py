from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PricingUiContractTests(unittest.TestCase):
    def setUp(self):
        self.pricing = json.loads((ROOT / "PRICING.json").read_text(encoding="utf-8"))
        self.readiness = json.loads((ROOT / "COMMERCE_READINESS.json").read_text(encoding="utf-8"))
        self.witness = json.loads((ROOT / "FOREIGN_AGENT_WITNESS.json").read_text(encoding="utf-8"))
        self.product = json.loads((ROOT / "products/JANUS.SEARCH.json").read_text(encoding="utf-8"))
        self.payment_policy = (ROOT / "PAYMENT_POLICY.md").read_text(encoding="utf-8")
        self.js = (ROOT / "assets/pricing-v1.js").read_text(encoding="utf-8")
        self.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_ratecard_is_machine_readable_and_state_matches_commerce_gate(self):
        self.assertEqual(self.pricing["schema"], "janus.machine_market.pricing.v1")
        self.assertEqual(self.pricing["currency"], "USDT")
        self.assertEqual(self.pricing["chain_id"], 1)
        self.assertGreater(self.pricing["quote_ttl_seconds"], 0)
        live = self.witness["foreign_agent_witness"] is True
        if live:
            self.assertEqual(self.pricing["status"], "MIXED_JANUS_SEARCH_LIVE_OTHER_SKUS_PREVIEW")
            self.assertEqual(self.pricing["live_skus"], ["JANUS.SEARCH"])
            self.assertTrue(self.readiness["money_enabled"])
            self.assertTrue(self.product["machine_purchase"])
        else:
            self.assertEqual(self.pricing["status"], "PREVIEW_RATECARD_NOT_LIVE")
            self.assertFalse(self.readiness["money_enabled"])
            self.assertFalse(self.product["machine_purchase"])

    def test_declared_receiver_matches_canonical_payment_policy(self):
        address = self.pricing["declared_receiving_address"]
        self.assertIn(address, self.payment_policy)
        self.assertEqual(address.lower(), self.readiness["payment_rail"]["declared_receiving_address"].lower())
        self.assertEqual(self.pricing["token_contract"].lower(), self.readiness["payment_rail"]["token_contract"].lower())

    def test_bounded_services_have_integer_micro_usdt_prices_and_mode_multipliers(self):
        for sku in (
            "JANUS.SEARCH",
            "JANUS.DATASET_SCOUT",
            "JANUS.EVIDENCE_PACK",
            "JANUS.ARCHIVE_SCAN",
            "JANUS.REPO_AUDIT",
            "JANUS.RESEARCH_JOB",
        ):
            product = self.pricing["products"][sku]
            self.assertIsInstance(product["base_unit_usdt_micros"], int)
            self.assertGreater(product["base_unit_usdt_micros"], 0)
            self.assertTrue(product["modes"])
            for mode in product["modes"].values():
                self.assertIsInstance(mode["multiplier_bps"], int)
                self.assertGreater(mode["multiplier_bps"], 0)

    def test_volume_discount_tiers_are_monotonic(self):
        tiers = self.pricing["quantity_discounts"]
        quantities = [x["min_quantity"] for x in tiers]
        discounts = [x["discount_bps"] for x in tiers]
        self.assertEqual(quantities, sorted(quantities))
        self.assertEqual(discounts, sorted(discounts))
        self.assertLess(max(discounts), 10000)

    def test_closed_and_delegated_products_do_not_get_local_checkout_prices(self):
        self.assertIsNone(self.pricing["products"]["JANUS.INFERENCE"]["local_price"])
        self.assertIsNone(self.pricing["products"]["JANUS.COMPUTE"]["local_price"])
        self.assertIsNone(self.pricing["products"]["HELIOS.PILOT"]["local_price"])
        self.assertEqual(self.pricing["products"]["HELIOS.PILOT"]["authority"], "DELEGATED_TO_JANUS_HELIOS")

    def test_pages_load_pricing_after_store_execution_bridge(self):
        store = self.html.index('src="assets/store-exec-v1.js"')
        pricing = self.html.index('src="assets/pricing-v1.js"')
        self.assertLess(store, pricing)
        self.assertIn('href="PRICING.json"', self.html)

    def test_browser_quote_remains_non_authoritative_in_both_commerce_states(self):
        for token in (
            "browser preview is not a payable invoice",
            "COMMERCE_READINESS.json",
            "FROZEN QUOTE PREVIEW",
            "total_usdt_micros",
        ):
            self.assertIn(token, self.js)
        self.assertIn("PAYMENT != COMMAND", self.payment_policy)
        self.assertIn("UNSOLICITED PAYMENT GRANTS NOTHING", self.payment_policy)


if __name__ == "__main__":
    unittest.main()
