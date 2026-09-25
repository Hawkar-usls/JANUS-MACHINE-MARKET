from __future__ import annotations

import unittest

from runtime.public_pr_review_beta import (
    GLOBAL_DAILY_LIMIT,
    FIRST_FREE_PER_ACTOR,
    PUBLIC_ORIGIN,
    evaluate_admission,
    normalize_public_request,
)

class PublicPRReviewBetaTest(unittest.TestCase):
    def issue(self, login="external-agent", issue_id=100, number=10, created_at="2026-09-25T16:00:00Z"):
        return {"id":issue_id,"number":number,"created_at":created_at,"user":{"login":login}}

    def request(self):
        return {
            "schema":"janus.pr_review.public_request.v1",
            "repository":"example/repo",
            "pull_number":7,
            "expected_head_sha":"a"*40,
        }

    def test_normalize_external(self):
        r=normalize_public_request(self.issue(),self.request())
        self.assertEqual(r["request_origin"],PUBLIC_ORIGIN)
        self.assertEqual(r["buyer_actor_id"],"github:external-agent")
        self.assertEqual(r["pull_number"],7)

    def test_owner_rejected(self):
        with self.assertRaises(ValueError):
            normalize_public_request(self.issue(login="Hawkar-usls"),self.request())

    def test_first_free(self):
        req=normalize_public_request(self.issue(),self.request())
        self.assertTrue(evaluate_admission(req,[])["admitted"])
        receipt={
            "request_origin":PUBLIC_ORIGIN,
            "buyer_actor_id":"github:external-agent",
            "source_issue_id":99,
            "requested_at":"2026-09-24T12:00:00Z",
            "repository":"x/y","pull_number":1,"expected_head_sha":"b"*40,
        }
        d=evaluate_admission(req,[receipt])
        self.assertFalse(d["admitted"])
        self.assertEqual(d["reason"],"FIRST_FREE_PR_REVIEW_ALREADY_USED")

    def test_exact_retry(self):
        req=normalize_public_request(self.issue(),self.request())
        receipt={
            "request_origin":PUBLIC_ORIGIN,
            "buyer_actor_id":req["buyer_actor_id"],
            "source_issue_id":req["source_issue_id"],
            "requested_at":req["created_at"],
            "repository":req["repository"],
            "pull_number":req["pull_number"],
            "expected_head_sha":req["expected_head_sha"],
        }
        d=evaluate_admission(req,[receipt])
        self.assertTrue(d["admitted"])
        self.assertEqual(d["reason"],"EXACT_RETRY_ALREADY_DELIVERED")

    def test_daily_cap(self):
        req=normalize_public_request(self.issue(login="fresh-agent"),self.request())
        receipts=[]
        for i in range(GLOBAL_DAILY_LIMIT):
            receipts.append({
                "request_origin":PUBLIC_ORIGIN,
                "buyer_actor_id":f"github:other-{i}",
                "source_issue_id":1000+i,
                "requested_at":"2026-09-25T01:00:00Z",
            })
        d=evaluate_admission(req,receipts)
        self.assertFalse(d["admitted"])
        self.assertEqual(d["reason"],"GLOBAL_DAILY_LIMIT_REACHED")

    def test_policy_constants(self):
        self.assertEqual(FIRST_FREE_PER_ACTOR,1)
        self.assertEqual(GLOBAL_DAILY_LIMIT,10)

if __name__=="__main__":
    unittest.main()
