from __future__ import annotations

import unittest

from runtime.r1b_shadow_buyer_query import (
    ShadowBuyerQueryError,
    build_shadow_packet,
    verify_shadow_packet,
)


class R1BShadowBuyerQueryTest(unittest.TestCase):
    def request(self, **updates):
        value = {
            "schema": "janus.machine_market.buyer_query_shadow_request.v1",
            "request_id": "github-issue-42",
            "sku": "JANUS.SEARCH",
            "buyer_actor_id": "github:Hawkar-usls",
            "conversation_id": "market-shadow-42",
            "turn_index": 0,
            "message_text": "Какие слабые места ты видишь в этой гипотезе?",
            "created_at": "2026-08-31T06:30:00Z",
            "max_turns": 1,
            "source_issue_number": 42,
            "source_issue_id": 4242,
            "request_origin": "SELF_OWNER_SHADOW",
        }
        value.update(updates)
        return value

    def test_exact_same_request_is_exact_same_packet(self):
        a = build_shadow_packet(self.request())
        b = build_shadow_packet(self.request())
        self.assertEqual(a, b)
        self.assertTrue(verify_shadow_packet(a))

    def test_message_change_changes_query_identity(self):
        a = build_shadow_packet(self.request())
        b = build_shadow_packet(self.request(message_text="Другой вопрос"))
        self.assertNotEqual(a["query_id"], b["query_id"])
        self.assertNotEqual(a["query_hash"], b["query_hash"])
        self.assertNotEqual(a["packet_hash"], b["packet_hash"])

    def test_grant_is_read_only_not_execution_authority(self):
        packet = build_shadow_packet(self.request())
        grant = packet["purchase_grant"]
        entitlement = grant["buyer_query_entitlement"]
        self.assertFalse(grant["execution_authority_granted"])
        self.assertTrue(entitlement["read_only_conversation"])
        self.assertFalse(entitlement["external_effect_authorized"])
        self.assertFalse(packet["command_authority_granted"])
        self.assertFalse(packet["external_effect_authorized"])
        self.assertFalse(packet["money_enabled"])

    def test_tamper_fails_verification(self):
        packet = build_shadow_packet(self.request())
        packet["buyer_query"]["message_text"] = "tampered"
        self.assertFalse(verify_shadow_packet(packet))

    def test_wrong_sku_fails_closed(self):
        with self.assertRaisesRegex(ShadowBuyerQueryError, "R1B_ONLY_JANUS_SEARCH_ALLOWED"):
            build_shadow_packet(self.request(sku="JANUS.COMPUTE"))

    def test_turn_budget_fails_closed(self):
        with self.assertRaisesRegex(ShadowBuyerQueryError, "R1B_TURN_BUDGET_EXHAUSTED"):
            build_shadow_packet(self.request(turn_index=1, max_turns=1))

    def test_message_limit_fails_closed(self):
        with self.assertRaisesRegex(ShadowBuyerQueryError, "R1B_MESSAGE_EXCEEDS_ENTITLEMENT"):
            build_shadow_packet(self.request(message_text="x" * 101, max_message_utf8_bytes=100))


if __name__ == "__main__":
    unittest.main()
