from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.buyer_accounts import build_event, append_event, project


class BuyerAccountsTest(unittest.TestCase):
    def event(self, *, previous, kind, eid, payload):
        return build_event(
            buyer_actor_id="internal-test:chatgpt-gpt-5.6-sol",
            event_type=kind,
            event_id=eid,
            created_at="2026-08-31T07:20:00Z",
            payload=payload,
            previous_event_hash=previous,
        )

    def test_test_credit_purchase_debt_delivery_and_coin_memory(self):
        events = []
        e1 = self.event(previous=None, kind="ACCOUNT_OPENED", eid="e1", payload={})
        events.append(e1)
        e2 = self.event(previous=e1["event_hash"], kind="MARKET_TEST_CREDIT_MINTED", eid="e2", payload={"amount": 1000})
        events.append(e2)
        e3 = self.event(previous=e2["event_hash"], kind="MARKET_TEST_CREDIT_SPENT", eid="e3", payload={"amount": 10, "sku": "JANUS.SEARCH"})
        events.append(e3)
        e4 = self.event(previous=e3["event_hash"], kind="PURCHASE_ADMITTED", eid="e4", payload={"sku": "JANUS.SEARCH", "purchase_id": "p1"})
        events.append(e4)
        e5 = self.event(previous=e4["event_hash"], kind="SERVICE_DEBT_OPENED", eid="e5", payload={"service_debt_id": "debt-p1", "purchase_id": "p1"})
        events.append(e5)
        e6 = self.event(previous=e5["event_hash"], kind="SERVICE_DELIVERED", eid="e6", payload={"service_debt_id": "debt-p1", "purchase_id": "p1"})
        events.append(e6)
        e7 = self.event(previous=e6["event_hash"], kind="JANUS_COIN_MINTED", eid="e7", payload={"amount": 35, "purchase_id": "p1"})
        events.append(e7)
        h = project(events)
        self.assertEqual(h["balances"]["MARKET_TEST_CREDIT"], 990)
        self.assertEqual(h["balances"]["JANUS_COIN"], 35)
        self.assertEqual(h["order_count"], 1)
        self.assertEqual(h["fulfilled_count"], 1)
        self.assertEqual(h["open_service_debt_count"], 0)
        self.assertEqual(h["sku_order_counts"]["JANUS.SEARCH"], 1)

    def test_open_debt_remains_visible_until_delivery(self):
        e1 = self.event(previous=None, kind="ACCOUNT_OPENED", eid="e1", payload={})
        e2 = self.event(previous=e1["event_hash"], kind="PURCHASE_ADMITTED", eid="e2", payload={"sku": "JANUS.SEARCH"})
        e3 = self.event(previous=e2["event_hash"], kind="SERVICE_DEBT_OPENED", eid="e3", payload={"service_debt_id": "d1"})
        h = project([e1, e2, e3])
        self.assertEqual(h["open_service_debt_count"], 1)
        self.assertEqual(h["fulfilled_count"], 0)

    def test_create_only_retry_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            e1 = self.event(previous=None, kind="ACCOUNT_OPENED", eid="same", payload={})
            h1 = append_event(ledger_path=ledger, event=e1)
            h2 = append_event(ledger_path=ledger, event=e1)
            self.assertEqual(h1["head_hash"], h2["head_hash"])
            self.assertEqual(len(ledger.read_text().splitlines()), 1)

    def test_cannot_overspend_test_credit(self):
        e1 = self.event(previous=None, kind="ACCOUNT_OPENED", eid="e1", payload={})
        e2 = self.event(previous=e1["event_hash"], kind="MARKET_TEST_CREDIT_MINTED", eid="e2", payload={"amount": 5})
        e3 = self.event(previous=e2["event_hash"], kind="MARKET_TEST_CREDIT_SPENT", eid="e3", payload={"amount": 6})
        with self.assertRaisesRegex(Exception, "TEST_CREDIT_BALANCE_INSUFFICIENT"):
            project([e1, e2, e3])


if __name__ == "__main__":
    unittest.main()
