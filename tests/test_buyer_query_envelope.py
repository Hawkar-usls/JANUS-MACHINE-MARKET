from __future__ import annotations

import unittest

from runtime.buyer_query_envelope import BuyerQueryError, build_query


class BuyerQueryEnvelopeTest(unittest.TestCase):
    def grant(self):
        return {
            "schema": "janus.machine_market.purchase_grant.v1",
            "purchase_id": "pur-test-001",
            "sku": "JANUS.SEARCH",
            "offer_hash": "a" * 64,
            "request_hash": "b" * 64,
            "terms_hash": None,
            "payment_reference": "shadow-not-payment",
            "status": "PURCHASE_ELIGIBLE",
            "execution_authority_granted": False,
            "allowed_operation": "REQUEST_BOUNDED_BUYER_QUERY",
            "authority_ceiling": {
                "external_effects": False,
                "production_activator_authority": False,
            },
            "buyer_query_entitlement": {
                "enabled": True,
                "buyer_actor_id": "buyer:test-agent",
                "max_turns": 2,
                "max_message_utf8_bytes": 128,
                "max_answer_utf8_bytes": 1024,
                "conversation_history_turns": 4,
                "entitlement_nonce": "0123456789abcdef",
                "read_only_conversation": True,
                "external_effect_authorized": False,
            },
            "expires_at": None,
            "reasons": ["TEST_ONLY_SHADOW_GRANT"],
        }

    def build(self, **kw):
        args = dict(
            buyer_actor_id="buyer:test-agent",
            conversation_id="conv-1",
            turn_index=0,
            message_text="Что ты думаешь об этой гипотезе?",
            conversation_history=[],
        )
        args.update(kw)
        return build_query(self.grant(), **args)

    def test_deterministic_query_identity(self):
        a = self.build()
        b = self.build()
        self.assertEqual(a["query_id"], b["query_id"])
        self.assertEqual(a["query_hash"], b["query_hash"])
        self.assertEqual(a["purchase_grant_hash"], b["purchase_grant_hash"])

    def test_message_change_changes_query_identity(self):
        a = self.build()
        b = self.build(message_text="Другой вопрос")
        self.assertNotEqual(a["message_hash"], b["message_hash"])
        self.assertNotEqual(a["query_id"], b["query_id"])

    def test_turn_change_changes_query_identity(self):
        a = self.build(turn_index=0)
        b = self.build(turn_index=1)
        self.assertNotEqual(a["query_id"], b["query_id"])

    def test_wrong_buyer_fails_closed(self):
        with self.assertRaisesRegex(BuyerQueryError, "BUYER_ACTOR_NOT_ENTITLED"):
            self.build(buyer_actor_id="buyer:someone-else")

    def test_turn_budget_fails_closed(self):
        with self.assertRaisesRegex(BuyerQueryError, "QUERY_TURN_BUDGET_EXHAUSTED"):
            self.build(turn_index=2)

    def test_message_size_fails_closed(self):
        with self.assertRaisesRegex(BuyerQueryError, "BUYER_QUERY_TEXT_SIZE_EXCEEDED"):
            self.build(message_text="x" * 129)

    def test_no_entitlement_fails_closed(self):
        grant = self.grant()
        grant["buyer_query_entitlement"] = None
        with self.assertRaisesRegex(BuyerQueryError, "BUYER_QUERY_ENTITLEMENT_REQUIRED"):
            build_query(
                grant,
                buyer_actor_id="buyer:test-agent",
                conversation_id="conv-1",
                turn_index=0,
                message_text="hello",
            )

    def test_purchase_grant_never_grants_execution_authority(self):
        grant = self.grant()
        grant["execution_authority_granted"] = True
        with self.assertRaisesRegex(BuyerQueryError, "PURCHASE_GRANT_MUST_NOT_GRANT_EXECUTION_AUTHORITY"):
            build_query(
                grant,
                buyer_actor_id="buyer:test-agent",
                conversation_id="conv-1",
                turn_index=0,
                message_text="hello",
            )


if __name__ == "__main__":
    unittest.main()
