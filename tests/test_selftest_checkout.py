from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.selftest_checkout import SELFTEST_COST, run_checkout


class SelftestCheckoutTest(unittest.TestCase):
    def setUp(self):
        self.agent = {
            "agent_id": "internal-test:chatgpt-gpt-5.6-sol",
            "initial_test_credit": 1000000,
        }

    def _products(self, root: Path):
        rows = [
            ("JANUS.SEARCH", "PAID_RUNTIME_ARMED_PRICE_AND_MERGE_GATES_PENDING"),
            ("JANUS.DATASET_SCOUT", "SPECIFICATION_READY"),
            ("JANUS.EVIDENCE_PACK", "SPECIFICATION_READY"),
            ("JANUS.ARCHIVE_SCAN", "SPECIFICATION_READY"),
            ("JANUS.REPO_AUDIT", "SPECIFICATION_READY"),
            ("JANUS.RESEARCH_JOB", "SPECIFICATION_READY"),
            ("JANUS.INFERENCE", "CLOSED_TARGET_EXECUTION_WITNESS_PENDING"),
            ("JANUS.COMPUTE", "CLOSED_TARGET_EXECUTION_WITNESS_PENDING"),
            ("HELIOS.PILOT", "DELEGATED_ARMED_DISABLED"),
        ]
        for sku, status in rows:
            (root / f"{sku}.json").write_text(json.dumps({"sku": sku, "status": status}), encoding="utf-8")

    def test_only_live_search_consumes_credit_and_opens_debt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._products(root)
            out = run_checkout(agent=self.agent, products_dir=root)
        by_sku = {r["sku"]: r for r in out["results"]}
        self.assertEqual(by_sku["JANUS.SEARCH"]["status"], "ADMITTED_AWAITING_VERIFIED_RESULT")
        self.assertEqual(by_sku["JANUS.SEARCH"]["spent"], SELFTEST_COST)
        self.assertEqual(by_sku["JANUS.DATASET_SCOUT"]["spent"], 0)
        self.assertEqual(by_sku["JANUS.INFERENCE"]["status"], "BLOCKED_CLOSED")
        self.assertEqual(by_sku["HELIOS.PILOT"]["status"], "EXCLUDED_BY_USER")
        head = out["account_head"]
        self.assertEqual(head["balances"]["MARKET_TEST_CREDIT"], 1000000 - SELFTEST_COST)
        self.assertEqual(head["order_count"], 1)
        self.assertEqual(head["open_service_debt_count"], 1)
        self.assertEqual(head["fulfilled_count"], 0)

    def test_verified_search_receipt_closes_debt(self):
        receipt = {
            "sku": "JANUS.SEARCH",
            "verified": True,
            "result_identity": "tr-test",
            "receipt_hash": "a" * 64,
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._products(root)
            out = run_checkout(agent=self.agent, products_dir=root, verified_search_receipt=receipt)
        row = next(r for r in out["results"] if r["sku"] == "JANUS.SEARCH")
        self.assertEqual(row["status"], "FULFILLED_VERIFIED_RESULT")
        self.assertEqual(out["account_head"]["open_service_debt_count"], 0)
        self.assertEqual(out["account_head"]["fulfilled_count"], 1)

    def test_bad_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._products(root)
            with self.assertRaisesRegex(ValueError, "SELFTEST_SEARCH_RECEIPT_INVALID"):
                run_checkout(agent=self.agent, products_dir=root, verified_search_receipt={"sku":"JANUS.SEARCH","verified":False})


if __name__ == "__main__":
    unittest.main()
