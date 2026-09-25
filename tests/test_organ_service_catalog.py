from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]

SPECIALISTS = {
    "JANUS.TOPA_HUNT": ("Hawkar-usls/TOPA", "main"),
    "JANUS.DEMIURGE_SCOUT": ("Hawkar-usls/Janus-Demiurge", "main"),
    "JANUS.COUSTEAU_SCAN": ("Hawkar-usls/Janus-Cosmos", "janus-echo-cousteau"),
    "JANUS.META_REGISTRY_SEARCH": ("Hawkar-usls/janus-meta-registry", "main"),
    "JANUS.FUNDAMENTUM_AUDIT": ("Hawkar-usls/Janus-Fundamentum", "main"),
    "JANUS.SWARM_RESEARCH": ("Hawkar-usls/janus-distributed-ai-swarm", "main"),
}

class OrganServiceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "CATALOG.json").read_text(encoding="utf-8"))
        self.matrix = json.loads((ROOT / "ORGAN_SERVICE_MATRIX.json").read_text(encoding="utf-8"))
        self.pricing = json.loads((ROOT / "PRICING.json").read_text(encoding="utf-8"))
        self.store_js = (ROOT / "assets/store-exec-v1.js").read_text(encoding="utf-8")

    def test_specialist_services_are_discoverable_but_not_live_or_purchasable(self):
        rows = {x["sku"]: x for x in self.catalog["products"]}
        for sku, (repository, ref) in SPECIALISTS.items():
            self.assertIn(sku, rows)
            self.assertEqual(rows[sku]["status"], "ROUTER_PREPARED_EXECUTION_RECEIPT_REQUIRED")
            self.assertTrue(rows[sku]["machine_discovery"])
            self.assertFalse(rows[sku]["machine_purchase"])
            p = json.loads((ROOT / f"products/{sku}.json").read_text(encoding="utf-8"))
            self.assertEqual(p["source"]["repository"], repository)
            self.assertEqual(p["source"]["ref"], ref)
            self.assertFalse(p["machine_purchase"])
            self.assertFalse(p["execution"]["public_live"])
            self.assertEqual(p["execution"]["blocker"], "DEDICATED_SPECIALIST_BRIDGE_AND_END_TO_END_RETURN_RECEIPT")

    def test_cousteau_is_bound_to_real_ocean_branch(self):
        c = self.matrix["services"]["JANUS.COUSTEAU_SCAN"]
        self.assertEqual(c["organ"], "Hawkar-usls/Janus-Cosmos")
        self.assertEqual(c["ref"], "janus-echo-cousteau")
        self.assertIn("bathymetry", c["role"])
        self.assertFalse(c["public_live"])

    def test_specialist_prices_are_reference_only_and_not_payable(self):
        for sku in SPECIALISTS:
            p = self.pricing["products"][sku]
            self.assertEqual(p["status"], "REFERENCE_ONLY_NOT_LIVE")
            self.assertEqual(p["pricing_alias"], "JANUS.RESEARCH_JOB")
            self.assertIsNone(p["local_price"])

    def test_specialists_do_not_leak_into_live_home_services(self):
        start = self.store_js.index("const LIVE_HOME_SERVICES")
        end = self.store_js.index("function q(", start)
        live_block = self.store_js[start:end]
        for sku in SPECIALISTS:
            self.assertNotIn(sku, live_block)
        for sku in ("JANUS.SEARCH", "JANUS.PR_REVIEW", "JANUS.REPO_AUDIT", "JANUS.DATASET_SCOUT"):
            self.assertIn(sku, live_block)

    def test_pr_review_is_public_but_not_a_specialist_organ(self):
        pr = self.matrix["services"]["JANUS.PR_REVIEW"]
        self.assertTrue(pr["public_live"])
        self.assertFalse(pr["machine_purchase"])
        self.assertIn("pull-request", pr["role"])
        self.assertFalse(json.loads((ROOT / "products/JANUS.PR_REVIEW.json").read_text(encoding="utf-8"))["execution"]["paid_execution"])

    def test_first_free_search_is_separate_from_specialist_catalog(self):
        search = self.matrix["services"]["JANUS.SEARCH"]
        self.assertTrue(search["public_live"])
        self.assertEqual(search["first_free_per_external_principal"], 1)
        for sku in SPECIALISTS:
            self.assertFalse(self.matrix["services"][sku]["public_live"])

    def test_truth_laws_are_fail_closed(self):
        laws = set(self.matrix["routing_laws"])
        for law in (
            "ORGAN_CAPABILITY != LIVE_MARKET_EXECUTION",
            "ROUTE_PROPOSAL != DISPATCH_AUTHORITY",
            "DISCOVERABLE != PURCHASABLE != EXECUTION_AUTHORITY != EXECUTION_WITNESS",
        ):
            self.assertIn(law, laws)

if __name__ == "__main__":
    unittest.main()
