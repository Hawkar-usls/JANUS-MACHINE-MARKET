from datetime import datetime, timezone
import unittest

from runtime.public_search_beta import (
    GLOBAL_DAILY_LIMIT,
    MAX_ANSWER_UTF8_BYTES,
    MAX_MESSAGE_UTF8_BYTES,
    PER_ACTOR_DAILY_LIMIT,
    PUBLIC_ORIGIN,
    PublicSearchBetaError,
    evaluate_outbox_admission,
    normalize_external_issue_request,
)
from runtime.r1b_shadow_buyer_query import build_shadow_packet, verify_shadow_packet


class PublicSearchBetaTests(unittest.TestCase):
    def issue(self, *, login="external-user", issue_id=1001, issue_number=41, created_at="2026-09-04T10:00:00Z"):
        return {
            "id": issue_id,
            "number": issue_number,
            "created_at": created_at,
            "user": {"login": login, "id": 9001, "type": "User"},
        }

    def raw_request(self, message="find public datasets about comet observations"):
        return {
            "schema": "janus.machine_market.buyer_query_shadow_request.v1",
            "conversation_id": "untrusted-client-choice",
            "turn_index": 7,
            "message_text": message,
            "max_turns": 8,
            "max_message_utf8_bytes": 8000,
            "max_answer_utf8_bytes": 12000,
            "conversation_history_turns": 8,
        }

    def packet(self, *, login="external-user", issue_id=1001, issue_number=41, created_at="2026-09-04T10:00:00Z", message="hello"):
        req = normalize_external_issue_request(
            self.issue(login=login, issue_id=issue_id, issue_number=issue_number, created_at=created_at),
            self.raw_request(message),
        )
        packet = build_shadow_packet(req)
        self.assertTrue(verify_shadow_packet(packet))
        return packet

    def test_external_request_is_server_normalized_and_bounded(self):
        req = normalize_external_issue_request(self.issue(), self.raw_request())
        self.assertEqual(req["request_origin"], PUBLIC_ORIGIN)
        self.assertEqual(req["buyer_actor_id"], "github:external-user")
        self.assertEqual(req["request_id"], "github-issue-id:1001")
        self.assertEqual(req["conversation_id"], "public-market-issue-1001")
        self.assertEqual(req["turn_index"], 0)
        self.assertEqual(req["max_turns"], 1)
        self.assertEqual(req["conversation_history_turns"], 0)
        self.assertEqual(req["max_message_utf8_bytes"], MAX_MESSAGE_UTF8_BYTES)
        self.assertEqual(req["max_answer_utf8_bytes"], MAX_ANSWER_UTF8_BYTES)

    def test_owner_cannot_enter_public_beta_path(self):
        with self.assertRaisesRegex(PublicSearchBetaError, "PUBLIC_BETA_OWNER_MUST_USE_OWNER_SHADOW"):
            normalize_external_issue_request(self.issue(login="Hawkar-usls"), self.raw_request())

    def test_message_limit_is_enforced_before_home_packet(self):
        with self.assertRaisesRegex(PublicSearchBetaError, "PUBLIC_BETA_MESSAGE_TOO_LARGE"):
            normalize_external_issue_request(self.issue(), self.raw_request("x" * (MAX_MESSAGE_UTF8_BYTES + 1)))

    def test_first_request_is_admitted_and_exact_retry_is_idempotent(self):
        packet = self.packet()
        first = evaluate_outbox_admission(packet, [])
        self.assertTrue(first["admitted"])
        retry = evaluate_outbox_admission(packet, [packet])
        self.assertTrue(retry["admitted"])
        self.assertTrue(retry["exact_retry"])
        self.assertEqual(retry["reason"], "EXACT_RETRY")

    def test_same_issue_cannot_be_rebound_to_changed_query(self):
        first = self.packet(message="first")
        changed = self.packet(message="changed")
        decision = evaluate_outbox_admission(changed, [first])
        self.assertFalse(decision["admitted"])
        self.assertEqual(decision["reason"], "ISSUE_ALREADY_BOUND_TO_DIFFERENT_QUERY")

    def test_per_actor_daily_quota(self):
        priors = [
            self.packet(issue_id=2000 + i, issue_number=50 + i, message=f"q{i}")
            for i in range(PER_ACTOR_DAILY_LIMIT)
        ]
        current = self.packet(issue_id=3000, issue_number=90, message="over")
        decision = evaluate_outbox_admission(current, priors)
        self.assertFalse(decision["admitted"])
        self.assertEqual(decision["reason"], "PER_ACTOR_DAILY_LIMIT_REACHED")

    def test_global_daily_quota(self):
        priors = [
            self.packet(login=f"user-{i}", issue_id=4000 + i, issue_number=100 + i, message=f"q{i}")
            for i in range(GLOBAL_DAILY_LIMIT)
        ]
        current = self.packet(login="new-user", issue_id=9000, issue_number=999, message="over")
        decision = evaluate_outbox_admission(current, priors)
        self.assertFalse(decision["admitted"])
        self.assertEqual(decision["reason"], "GLOBAL_DAILY_LIMIT_REACHED")

    def test_previous_day_does_not_consume_today_quota(self):
        priors = [
            self.packet(issue_id=6000 + i, issue_number=300 + i, created_at="2026-09-03T23:59:00Z", message=f"q{i}")
            for i in range(PER_ACTOR_DAILY_LIMIT)
        ]
        current = self.packet(issue_id=7000, issue_number=400, created_at="2026-09-04T00:01:00Z", message="today")
        self.assertTrue(evaluate_outbox_admission(current, priors)["admitted"])


if __name__ == "__main__":
    unittest.main()
