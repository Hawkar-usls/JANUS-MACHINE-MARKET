from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StorePagesExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.js = (ROOT / "assets/store-exec-v1.js").read_text(encoding="utf-8")

    def test_pages_uses_existing_buyer_conversation_contract(self):
        owner_workflow = (ROOT / ".github/workflows/r1b-buyer-query-shadow-outbox.yml").read_text(encoding="utf-8")
        public_workflow = (ROOT / ".github/workflows/r1-public-search-beta-outbox.yml").read_text(encoding="utf-8")
        public_policy = (ROOT / "runtime/public_search_beta.py").read_text(encoding="utf-8")
        for token in ("[JANUS R1B BUYER QUERY SHADOW]", "JANUS_BUYER_QUERY_SHADOW_JSON"):
            self.assertIn(token, self.js)
            self.assertIn(token, owner_workflow)
            self.assertIn(token, public_workflow)
        schema = "janus.machine_market.buyer_query_shadow_request.v1"
        self.assertIn(schema, self.js)
        self.assertIn(schema, owner_workflow)
        self.assertIn(schema, public_policy)
        self.assertIn("PHYSARIUS_CREDENTIALLESS_PULL", owner_workflow)
        self.assertIn("janus/market-home-outbox", public_workflow)

    def test_public_search_beta_remains_explicit_when_paid_search_later_goes_live(self):
        contract = json.loads((ROOT / "PUBLIC_SERVICE_BETA.json").read_text(encoding="utf-8"))
        ingress = json.loads((ROOT / "MACHINE_INGRESS.json").read_text(encoding="utf-8"))
        witness = json.loads((ROOT / "FOREIGN_AGENT_WITNESS.json").read_text(encoding="utf-8"))
        search = contract["public_services"]["JANUS.SEARCH"]
        self.assertEqual(search["status"], "PUBLIC_ZERO_PRICE_BETA")
        self.assertEqual(search["max_turns_per_issue"], 1)
        self.assertEqual(search["max_message_utf8_bytes"], 4000)
        self.assertEqual(search["max_answer_utf8_bytes"], 6000)
        self.assertEqual(search["per_actor_daily_limit"], 3)
        self.assertEqual(search["global_daily_limit"], 20)
        self.assertFalse(contract["authority"]["money_enabled"])
        self.assertFalse(contract["authority"]["command_authority_granted"])
        self.assertIn("owner_shadow", contract["not_public_yet"]["JANUS.REPO_AUDIT"].lower())
        self.assertIn("owner_shadow", contract["not_public_yet"]["JANUS.DATASET_SCOUT"].lower())
        if witness["foreign_agent_witness"] is True:
            self.assertEqual(ingress["live_services"]["JANUS.SEARCH"]["status"], "LIVE_PUBLIC_ZERO_PRICE_BETA_PLUS_PAID_ISSUE_CHECKOUT")
            self.assertEqual(ingress["live_services"]["JANUS.SEARCH"]["paid_checkout"]["status"], "LIVE_JANUS_SEARCH_ONLY")
        else:
            self.assertEqual(ingress["live_services"]["JANUS.SEARCH"]["status"], "LIVE_PUBLIC_ZERO_PRICE_BETA_PLUS_OWNER_SHADOW")
        self.assertIn("PUBLIC BETA", self.js)
        self.assertIn("OWNER SHADOW", self.js)

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

    def test_pages_declares_three_home_routes_and_no_implicit_multi_sku_authority(self):
        for sku in ("JANUS.SEARCH", "JANUS.REPO_AUDIT", "JANUS.DATASET_SCOUT"):
            self.assertIn(sku, self.js)
        self.assertIn("MULTI_SERVICE_NOT_YET_ATOMIC", self.js)
        self.assertIn("proof-carrying multi-SKU orchestration grant", self.js)

    def test_pages_loads_execution_bridge_after_base_site_logic(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        base = html.index('src="assets/site.js"')
        bridge = html.index('src="assets/store-exec-v1.js"')
        self.assertLess(base, bridge)

    def test_public_zero_price_path_remains_non_commanding_even_if_paid_search_is_live(self):
        for token in (
            "payment_required: `false`",
            "money_enabled: `false`",
            "command_authority_granted: `false`",
            "external_effect_authorized: `false`",
            "PURCHASE GRANT != EXECUTION AUTHORITY",
            "PUBLIC INTAKE != COMPLETED SERVICE",
        ):
            self.assertIn(token, self.js)

    def test_home_repository_and_public_outbox_contract_are_explicit(self):
        self.assertIn("Hawkar-usls/Hawkar-usls", self.js)
        for path in (
            ROOT / ".github/workflows/r1b-buyer-query-shadow-outbox.yml",
            ROOT / ".github/workflows/r1-public-search-beta-outbox.yml",
            ROOT / ".github/workflows/r2-repo-audit-shadow-outbox.yml",
            ROOT / ".github/workflows/r3-dataset-scout-shadow-outbox.yml",
        ):
            self.assertIn("janus/market-home-outbox", path.read_text(encoding="utf-8"))

    def test_external_customer_does_not_auto_promote_foreign_agent_witness(self):
        contract = json.loads((ROOT / "PUBLIC_SERVICE_BETA.json").read_text(encoding="utf-8"))
        joined = "\n".join(contract["truth_boundary"])
        self.assertIn("EXTERNAL_CUSTOMER != FOREIGN_AGENT_WITNESS_UNLESS_SEPARATE_INDEPENDENCE_GATE_PASSES", joined)


if __name__ == "__main__":
    unittest.main()
