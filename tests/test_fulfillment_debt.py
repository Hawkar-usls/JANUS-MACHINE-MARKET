from __future__ import annotations

import unittest

from runtime.fulfillment_debt import open_debt, transition, verify


class FulfillmentDebtTest(unittest.TestCase):
    def test_timeout_never_closes_paid_service_debt(self):
        d = open_debt(purchase_id="p1", query_id="q1", buyer_actor_id="buyer:a", sku="JANUS.SEARCH", created_at="2026-08-31T07:00:00Z")
        d = transition(d, event="TIMEOUT", at="2026-08-31T07:10:00Z")
        self.assertTrue(verify(d))
        self.assertFalse(d["closed"])
        self.assertEqual(d["state"], "SERVICE_DEBT_OPEN")
        self.assertEqual(d["retry_count"], 1)

    def test_normal_path_closes_only_after_buyer_delivery(self):
        d = open_debt(purchase_id="p1", query_id="q1", buyer_actor_id="buyer:a", sku="JANUS.SEARCH", created_at="2026-08-31T07:00:00Z")
        d = transition(d, event="OUTBOX_PUBLISHED", at="2026-08-31T07:01:00Z", binding="packet-hash")
        d = transition(d, event="HOME_ACCEPTED", at="2026-08-31T07:02:00Z")
        d = transition(d, event="JANUS_RESULT_SEALED", at="2026-08-31T07:03:00Z", binding="result-id")
        d = transition(d, event="MARKET_RECONCILED", at="2026-08-31T07:04:00Z", binding="market-receipt")
        self.assertFalse(d["closed"])
        d = transition(d, event="BUYER_DELIVERED", at="2026-08-31T07:05:00Z", binding="delivery-receipt")
        self.assertTrue(d["closed"])
        self.assertEqual(d["state"], "SERVICE_DEBT_CLOSED")
        self.assertEqual(d["close_reason"], "VERIFIED_BUYER_DELIVERY")

    def test_cannot_skip_directly_from_outbox_to_delivery(self):
        d = open_debt(purchase_id="p1", query_id="q1", buyer_actor_id="buyer:a", sku="JANUS.SEARCH", created_at="2026-08-31T07:00:00Z")
        d = transition(d, event="OUTBOX_PUBLISHED", at="2026-08-31T07:01:00Z", binding="packet-hash")
        with self.assertRaisesRegex(Exception, "SERVICE_DEBT_TRANSITION_FORBIDDEN"):
            transition(d, event="BUYER_DELIVERED", at="2026-08-31T07:02:00Z", binding="delivery")


if __name__ == "__main__":
    unittest.main()
