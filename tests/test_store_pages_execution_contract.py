from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StorePagesExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.js = (ROOT / "assets/store-exec-v1.js").read_text(encoding="utf-8")

    def test_pages_uses_existing_buyer_conversation_contract(self):
        workflow = (ROOT / ".github/workflows/r1b-buyer-query-shadow-outbox.yml").read_text(encoding="utf-8")
        for token in (
            "[JANUS R1B BUYER QUERY SHADOW]",
            "JANUS_BUYER_QUERY_SHADOW_JSON",
            "janus.machine_market.buyer_query_shadow_request.v1",
        ):
            self.assertIn(token, self.js)
            self.assertIn(token, workflow)
        self.assertIn("PHYSARIUS_CREDENTIALLESS_PULL", workflow)

    def test_pages_uses_existing_repo_audit_contract(self):
        workflow = (ROOT / ".github/workflows/r2-repo-audit-shadow-outbox.yml").read_text(encoding="utf-8")
        for token in ("[JANUS REPO AUDIT SHADOW]", "JANUS_REPO_AUDIT_SHADOW_JSON"):
            self.assertIn(token, self.js)
            self.assertIn(token, workflow)
        for field in ("repository", "ref", "max_tree_entries", "max_blob_files", "max_total_blob_bytes"):
            self.assertIn(field, self.js)
            self.assertIn(field, workflow)

    def test_pages_uses_existing_dataset_scout_contract(self):
        workflow = (ROOT / ".github/workflows/r3-dataset-scout-shadow-outbox.yml").read_text(encoding="utf-8")
        for token in ("[JANUS DATASET SCOUT SHADOW]", "JANUS_DATASET_SCOUT_SHADOW_JSON"):
            self.assertIn(token, self.js)
            self.assertIn(token, workflow)
        for field in ("query", "domain", "license_preferences", "format_preferences", "max_results", "max_catalogs", "per_catalog_timeout_seconds"):
            self.assertIn(field, self.js)
            self.assertIn(field, workflow)

    def test_pages_declares_three_live_home_services_and_no_implicit_multi_sku_authority(self):
        for sku in ("JANUS.SEARCH", "JANUS.REPO_AUDIT", "JANUS.DATASET_SCOUT"):
            self.assertIn(sku, self.js)
        self.assertIn("MULTI_SERVICE_NOT_YET_ATOMIC", self.js)
        self.assertIn("proof-carrying multi-SKU orchestration grant", self.js)

    def test_pages_loads_execution_bridge_after_base_site_logic(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        base = html.index('src="assets/site.js"')
        bridge = html.index('src="assets/store-exec-v1.js"')
        self.assertLess(base, bridge)

    def test_pages_truth_boundary_remains_zero_price_and_non_commanding(self):
        for token in (
            "payment_required: `false`",
            "money_enabled: `false`",
            "command_authority_granted: `false`",
            "external_effect_authorized: `false`",
            "PURCHASE GRANT != EXECUTION AUTHORITY",
        ):
            self.assertIn(token, self.js)

    def test_home_repository_and_public_outbox_contract_are_explicit(self):
        self.assertIn("Hawkar-usls/Hawkar-usls", self.js)
        for path in (
            ROOT / ".github/workflows/r1b-buyer-query-shadow-outbox.yml",
            ROOT / ".github/workflows/r2-repo-audit-shadow-outbox.yml",
            ROOT / ".github/workflows/r3-dataset-scout-shadow-outbox.yml",
        ):
            self.assertIn("janus/market-home-outbox", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
