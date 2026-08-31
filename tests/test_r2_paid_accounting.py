from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runtime.r2_paid_accounting import admit_paid_purchase, mark_outbox_published, reconcile_delivery


class PaidAccountingTest(unittest.TestCase):
    def packet(self):
        return {
            "schema": "janus.machine_market.home_paid_buyer_query_packet.v1",
            "mode": "PAID_ERC20",
            "money_enabled": True,
            "production_purchase": True,
            "query_id": "bq-paid-test",
            "query_hash": "a" * 64,
            "packet_hash": "b" * 64,
            "payment_receipt_hash": "c" * 64,
            "payment_receipt": {
                "payment_reference": "ethereum:1:0x" + "1" * 64 + ":7",
                "amount_atomic": 5900,
            },
            "purchase_grant": {"purchase_id": "pur-paid-test"},
            "buyer_query": {
                "buyer_actor_id": "github:test-buyer",
                "sku": "JANUS.SEARCH",
                "created_at": "2026-08-31T08:00:00Z",
            },
        }

    def reward_policy(self):
        return {
            "schema": "janus.machine_market.janus_coin_reward_policy.v1",
            "production_purchase_reward": {"usdt_atomic_per_coin": 1000},
        }

    def test_admit_retry_is_idempotent_and_delivery_mints_reward(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=self.packet()
            a1=admit_paid_purchase(packet=p,state_root=root)
            a2=admit_paid_purchase(packet=p,state_root=root)
            self.assertEqual(a1["profile_id"],a2["profile_id"])
            self.assertEqual(a2["open_service_debt_count"],1)
            debt=mark_outbox_published(state_root=root,service_debt_id=a1["service_debt_id"],packet_hash=p["packet_hash"],at="2026-08-31T08:01:00Z")
            self.assertEqual(debt["state"],"OUTBOX_PUBLISHED")

            ref=p["payment_receipt"]["payment_reference"]
            key=hashlib.sha256(ref.encode()).hexdigest()
            claim_dir=root/"state/r2-paid/payment-claims"; claim_dir.mkdir(parents=True)
            claim={
                "payment_reference":ref,
                "payment_receipt_hash":p["payment_receipt_hash"],
                "purchase_id":"pur-paid-test",
                "query_id":"bq-paid-test",
                "buyer_actor_id":"github:test-buyer",
                "amount_atomic":5900,
                "sku":"JANUS.SEARCH",
                "service_debt_id":a1["service_debt_id"],
            }
            (claim_dir/f"{key}.json").write_text(json.dumps(claim),encoding="utf-8")
            response={
                "purchase_id":"pur-paid-test",
                "query_id":"bq-paid-test",
                "payment_reference":ref,
                "home_response_hash":"d"*64,
                "buyer_query_receipt":{"execution_identity":"tr-test"},
            }
            d1=reconcile_delivery(response=response,state_root=root,buyer_delivery_receipt_hash="e"*64,delivered_at="2026-08-31T08:05:00Z",reward_policy=self.reward_policy())
            d2=reconcile_delivery(response=response,state_root=root,buyer_delivery_receipt_hash="e"*64,delivered_at="2026-08-31T08:05:00Z",reward_policy=self.reward_policy())
            self.assertTrue(d1["service_debt_closed"])
            self.assertEqual(d1["janus_coin_minted"],5)
            self.assertEqual(d1["janus_coin_balance"],5)
            self.assertEqual(d2["janus_coin_balance"],5)
            self.assertEqual(d2["fulfilled_count"],1)
            self.assertEqual(d2["open_service_debt_count"],0)


if __name__ == "__main__":
    unittest.main()
