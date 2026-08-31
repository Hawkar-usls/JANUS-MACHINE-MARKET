from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runtime.r2_paid_accounting import admit_paid_purchase, account_binding_path, mark_outbox_published, reconcile_delivery


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
            "return_route": {"source_issue_number": 123, "source_issue_id": 456},
        }

    def reward_policy(self):
        return {
            "schema": "janus.machine_market.janus_coin_reward_policy.v1",
            "production_purchase_reward": {
                "usdt_atomic_per_coin": 1000,
                "mint_trigger": "VERIFIED_BUYER_DELIVERY",
            },
        }

    def test_admit_retry_is_idempotent_and_delivery_mints_reward(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=self.packet()
            a1=admit_paid_purchase(packet=p,state_root=root)
            a2=admit_paid_purchase(packet=p,state_root=root)
            self.assertEqual(a1["profile_id"],a2["profile_id"])
            self.assertEqual(a2["open_service_debt_count"],1)
            binding=json.loads(account_binding_path(root,"pur-paid-test").read_text(encoding="utf-8"))
            self.assertEqual(binding["buyer_actor_id"],"github:test-buyer")
            self.assertEqual(binding["amount_atomic"],5900)
            self.assertEqual(binding["service_debt_id"],a1["service_debt_id"])
            self.assertEqual(binding["source_issue_number"],123)

            debt=mark_outbox_published(state_root=root,service_debt_id=a1["service_debt_id"],packet_hash=p["packet_hash"],at="2026-08-31T08:01:00Z")
            self.assertEqual(debt["state"],"OUTBOX_PUBLISHED")

            ref=p["payment_receipt"]["payment_reference"]
            key=hashlib.sha256(ref.encode()).hexdigest()
            claim_dir=root/"state/r2-paid/payment-claims"; claim_dir.mkdir(parents=True)
            # The immutable payment claim intentionally does NOT gain buyer-memory
            # or service-debt fields after creation.
            claim={
                "schema":"janus.machine_market.r2_payment_claim.v1",
                "payment_reference":ref,
                "payment_receipt_hash":p["payment_receipt_hash"],
                "purchase_id":"pur-paid-test",
                "purchase_grant_hash":"f"*64,
                "query_id":"bq-paid-test",
                "query_hash":p["query_hash"],
                "packet_hash":p["packet_hash"],
                "source_issue_number":123,
            }
            claim_path=claim_dir/f"{key}.json"
            claim_path.write_text(json.dumps(claim,sort_keys=True),encoding="utf-8")
            before=claim_path.read_bytes()

            response={
                "purchase_id":"pur-paid-test",
                "query_id":"bq-paid-test",
                "payment_reference":ref,
                "home_response_hash":"d"*64,
                "buyer_query_receipt":{"execution_identity":"tr-test"},
            }
            d1=reconcile_delivery(response=response,state_root=root,buyer_delivery_receipt_hash="e"*64,delivered_at="2026-08-31T08:05:00Z",reward_policy=self.reward_policy())
            d2=reconcile_delivery(response=response,state_root=root,buyer_delivery_receipt_hash="e"*64,delivered_at="2026-08-31T08:05:00Z",reward_policy=self.reward_policy())
            self.assertEqual(claim_path.read_bytes(),before)
            self.assertTrue(d1["service_debt_closed"])
            self.assertEqual(d1["janus_coin_minted"],5)
            self.assertEqual(d1["janus_coin_balance"],5)
            self.assertEqual(d2["janus_coin_balance"],5)
            self.assertEqual(d2["fulfilled_count"],1)
            self.assertEqual(d2["open_service_debt_count"],0)

    def test_account_binding_is_create_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=self.packet()
            admit_paid_purchase(packet=p,state_root=root)
            p["payment_receipt"]["amount_atomic"]=6000
            with self.assertRaisesRegex(Exception,"PAID_ACCOUNT_EVENT_PAYLOAD_CONFLICT|PAID_ACCOUNT_BINDING_CREATE_ONLY_CONFLICT"):
                admit_paid_purchase(packet=p,state_root=root)


if __name__ == "__main__":
    unittest.main()
