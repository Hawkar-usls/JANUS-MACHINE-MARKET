from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runtime.r2_paid_recovery import run


class PaidRecoveryTest(unittest.TestCase):
    def fixture(self, root: Path):
        state=root/"state-root"
        outbox=root/"outbox"
        ref="ethereum:1:0x"+"1"*64+":7"
        packet={
            "schema":"janus.machine_market.home_paid_buyer_query_packet.v1",
            "mode":"PAID_ERC20",
            "money_enabled":True,
            "production_purchase":True,
            "query_id":"bq-recovery-test",
            "query_hash":"a"*64,
            "packet_hash":"b"*64,
            "purchase_grant_hash":"c"*64,
            "payment_receipt_hash":"d"*64,
            "payment_receipt":{"payment_reference":ref,"amount_atomic":5900},
            "purchase_grant":{"purchase_id":"pur-recovery-test"},
            "buyer_query":{
                "buyer_actor_id":"github:recovery-buyer",
                "sku":"JANUS.SEARCH",
                "created_at":"2026-08-31T08:00:00Z"
            },
            "return_route":{"source_issue_number":321,"source_issue_id":654}
        }
        packet_dir=outbox/".janus/market-home-outbox"; packet_dir.mkdir(parents=True)
        (packet_dir/"bq-recovery-test.paid.packet.json").write_text(json.dumps(packet),encoding="utf-8")
        claim_dir=state/"state/r2-paid/payment-claims"; claim_dir.mkdir(parents=True)
        claim={
            "schema":"janus.machine_market.r2_payment_claim.v1",
            "payment_reference":ref,
            "payment_receipt_hash":packet["payment_receipt_hash"],
            "purchase_id":"pur-recovery-test",
            "purchase_grant_hash":packet["purchase_grant_hash"],
            "query_id":packet["query_id"],
            "query_hash":packet["query_hash"],
            "packet_hash":packet["packet_hash"],
            "source_issue_number":321,
        }
        key=hashlib.sha256(ref.encode()).hexdigest()
        claim_path=claim_dir/f"{key}.json"
        claim_path.write_text(json.dumps(claim,sort_keys=True),encoding="utf-8")
        reward=root/"reward.json"
        reward.write_text(json.dumps({
            "schema":"janus.machine_market.janus_coin_reward_policy.v1",
            "production_purchase_reward":{"usdt_atomic_per_coin":1000,"mint_trigger":"VERIFIED_BUYER_DELIVERY"}
        }),encoding="utf-8")
        return state,outbox,packet,claim_path,reward

    def test_recovery_opens_obligation_without_mutating_payment_claim(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); state,outbox,packet,claim_path,reward=self.fixture(root)
            before=claim_path.read_bytes()
            r=run(state_root=state,outbox_root=outbox,delivery_proofs_path=None,reward_policy_path=reward,now="2026-08-31T08:01:00Z")
            self.assertEqual(len(r["admitted_or_confirmed"]),1)
            self.assertEqual(r["open_service_debt_count"],1)
            self.assertFalse(r["second_cognition_authorized"])
            self.assertEqual(claim_path.read_bytes(),before)
            # Exact watchdog retry does not open a second account order or debt.
            r2=run(state_root=state,outbox_root=outbox,delivery_proofs_path=None,reward_policy_path=reward,now="2026-08-31T08:02:00Z")
            self.assertEqual(r2["open_service_debt_count"],1)
            account_heads=list((state/"state/accounts").glob("*/HEAD.json"))
            self.assertEqual(len(account_heads),1)
            head=json.loads(account_heads[0].read_text())
            self.assertEqual(head["order_count"],1)
            self.assertEqual(head["open_service_debt_count"],1)

    def test_delivery_proof_closes_debt_and_mints_bonus_once(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); state,outbox,packet,claim_path,reward=self.fixture(root)
            run(state_root=state,outbox_root=outbox,delivery_proofs_path=None,reward_policy_path=reward,now="2026-08-31T08:01:00Z")
            results=state/"state/r2-paid/results"; results.mkdir(parents=True)
            response={
                "purchase_id":"pur-recovery-test",
                "query_id":"bq-recovery-test",
                "payment_reference":packet["payment_receipt"]["payment_reference"],
                "home_response_hash":"e"*64,
                "buyer_query_receipt":{"execution_identity":"tr-recovery-test"}
            }
            (results/"bq-recovery-test.json").write_text(json.dumps(response),encoding="utf-8")
            proofs=root/"proofs.json"
            proofs.write_text(json.dumps({
                "bq-recovery-test":{
                    "purchase_id":"pur-recovery-test",
                    "buyer_delivery_receipt_hash":"f"*64,
                    "delivered_at":"2026-08-31T08:05:00Z"
                }
            }),encoding="utf-8")
            r=run(state_root=state,outbox_root=outbox,delivery_proofs_path=proofs,reward_policy_path=reward,now="2026-08-31T08:05:00Z")
            self.assertEqual(r["open_service_debt_count"],0)
            self.assertEqual(r["delivery_closed_or_confirmed"][0]["janus_coin_minted"],5)
            # Retry keeps one fulfillment and one reward mint.
            r2=run(state_root=state,outbox_root=outbox,delivery_proofs_path=proofs,reward_policy_path=reward,now="2026-08-31T08:06:00Z")
            self.assertEqual(r2["open_service_debt_count"],0)
            head=json.loads(next((state/"state/accounts").glob("*/HEAD.json")).read_text())
            self.assertEqual(head["fulfilled_count"],1)
            self.assertEqual(head["balances"]["JANUS_COIN"],5)

    def test_outbox_without_payment_claim_creates_no_buyer_obligation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); state,outbox,packet,claim_path,reward=self.fixture(root)
            claim_path.unlink()
            r=run(state_root=state,outbox_root=outbox,delivery_proofs_path=None,reward_policy_path=reward,now="2026-08-31T08:01:00Z")
            self.assertEqual(r["admitted_or_confirmed"],[])
            self.assertEqual(r["open_service_debt_count"],0)
            self.assertFalse((state/"state/accounts").exists())


if __name__ == "__main__":
    unittest.main()
