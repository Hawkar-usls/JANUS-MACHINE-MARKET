from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StorePagesExecutionContractTests(unittest.TestCase):
    def test_pages_uses_existing_market_to_home_issue_contract(self):
        js = (ROOT / "assets/store-exec-v1.js").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/r1b-buyer-query-shadow-outbox.yml").read_text(encoding="utf-8")

        for token in (
            "[JANUS R1B BUYER QUERY SHADOW]",
            "JANUS_BUYER_QUERY_SHADOW_JSON",
            "janus.machine_market.buyer_query_shadow_request.v1",
        ):
            self.assertIn(token, js)
            self.assertIn(token, workflow)

        self.assertIn("Hawkar-usls/Hawkar-usls", js)
        self.assertIn("janus/market-home-outbox", workflow)
        self.assertIn("PHYSARIUS_CREDENTIALLESS_PULL", workflow)

    def test_pages_loads_execution_bridge_after_base_site_logic(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        base = html.index('src="assets/site.js"')
        bridge = html.index('src="assets/store-exec-v1.js"')
        self.assertLess(base, bridge)

    def test_pages_truth_boundary_remains_zero_price_and_non_commanding(self):
        js = (ROOT / "assets/store-exec-v1.js").read_text(encoding="utf-8")
        for token in (
            "payment_required: `false`",
            "money_enabled: `false`",
            "command_authority_granted: `false`",
            "external_effect_authorized: `false`",
            "PURCHASE GRANT != EXECUTION AUTHORITY",
        ):
            self.assertIn(token, js)


if __name__ == "__main__":
    unittest.main()
