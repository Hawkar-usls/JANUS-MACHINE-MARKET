import json
import tempfile
import unittest
from pathlib import Path

from runtime.r1_shadow_search import run


ROOT = Path(__file__).resolve().parents[1]


def request(query="repository audit", request_id="req-shadow-001", purchase_id=None):
    value = {
        "schema": "janus.machine_market.request.v1",
        "request_id": request_id,
        "sku": "JANUS.SEARCH",
        "input": {
            "query": query,
            "source_scope": "MARKET_CATALOG",
            "max_results": 5
        },
        "requested_output": {"format": "application/json"},
        "max_runtime_seconds": 10,
        "created_at": "2026-08-31T00:00:00Z"
    }
    if purchase_id is not None:
        value["purchase_id"] = purchase_id
    return value


class R1ShadowSearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "market.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, value):
        return run(value, self.state, ROOT / "CATALOG.json", ROOT / "products")

    def test_exact_retry_reuses_one_execution_identity(self):
        first = self.invoke(request())
        second = self.invoke(request())
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(first["execution_id"], second["execution_id"])
        self.assertEqual(first["result_sha256"], second["result_sha256"])
        self.assertEqual(first["result_receipt"], second["result_receipt"])
        self.assertEqual(first["billable_execution_delta"], 1)
        self.assertEqual(second["billable_execution_delta"], 0)
        self.assertEqual(second["execution_count_for_purchase"], 1)

    def test_purchase_grant_never_becomes_execution_authority(self):
        out = self.invoke(request())
        grant = out["purchase_grant"]
        self.assertEqual(grant["status"], "PURCHASE_ELIGIBLE")
        self.assertIs(grant["execution_authority_granted"], False)
        self.assertIs(grant["authority_ceiling"]["production_activator_authority"], False)
        self.assertIs(out["result_receipt"]["execution_receipt"]["production_activator_authority"], False)

    def test_zero_price_and_no_payment_challenge(self):
        out = self.invoke(request())
        self.assertEqual(out["quote"]["price"]["amount"], "0")
        self.assertEqual(out["quote"]["price"]["asset"], "NONE")
        self.assertIsNone(out["quote"]["payment_challenge"])
        self.assertIsNone(out["result_receipt"]["payment_reference"])

    def test_bounded_catalog_search_returns_provenance(self):
        out = self.invoke(request("repository audit"))
        result = out["result"]
        self.assertEqual(result["source_scope"], "MARKET_CATALOG")
        self.assertLessEqual(result["match_count"], 5)
        self.assertIs(result["provenance"]["network_access_used"], False)
        self.assertIs(result["provenance"]["external_effects"], False)
        self.assertRegex(result["provenance"]["catalog_sha256"], r"^[0-9a-f]{64}$")

    def test_explicit_purchase_id_cannot_be_rebound(self):
        first = self.invoke(request())
        purchase_id = first["purchase_grant"]["purchase_id"]
        conflicting = request("dataset discovery", purchase_id=purchase_id)
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self.invoke(conflicting)

    def test_created_at_does_not_change_semantic_request_hash(self):
        one = request()
        two = request()
        two["created_at"] = "2099-01-01T00:00:00Z"
        first = self.invoke(one)
        second = self.invoke(two)
        self.assertEqual(first["request_hash"], second["request_hash"])
        self.assertTrue(second["replayed"])


if __name__ == "__main__":
    unittest.main()
