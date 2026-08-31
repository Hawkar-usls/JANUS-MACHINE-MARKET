from __future__ import annotations

import unittest
from pathlib import Path

from runtime.selftest_portfolio import build_matrix


class SelfTestPortfolioTest(unittest.TestCase):
    def test_all_products_accounted_for_without_touching_helios(self):
        m = build_matrix(Path("products"))
        rows = {row["sku"]: row for row in m["rows"]}
        self.assertEqual(rows["HELIOS.PILOT"]["test_action"], "EXCLUDED_BY_USER")
        self.assertEqual(rows["HELIOS.PILOT"]["expected"], "NOT_TOUCHED")
        self.assertEqual(rows["JANUS.SEARCH"]["expected"], "VERIFIED_RESULT_RECEIPT_REQUIRED")
        self.assertEqual(rows["JANUS.INFERENCE"]["expected"], "FAIL_CLOSED_NOT_PURCHASABLE")
        self.assertEqual(rows["JANUS.COMPUTE"]["expected"], "FAIL_CLOSED_NOT_PURCHASABLE")
        for sku in ("JANUS.DATASET_SCOUT", "JANUS.EVIDENCE_PACK", "JANUS.ARCHIVE_SCAN", "JANUS.REPO_AUDIT", "JANUS.RESEARCH_JOB"):
            self.assertEqual(rows[sku]["expected"], "BLOCK_SPECIFICATION_ONLY_NOT_YET_LIVE")


if __name__ == "__main__":
    unittest.main()
