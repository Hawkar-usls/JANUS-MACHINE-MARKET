from __future__ import annotations

import unittest

from runtime.r2_repo_audit_shadow import build_shadow_packet, verify_shadow_packet


class RepoAuditShadowTest(unittest.TestCase):
    def request(self):
        return {
            "buyer_actor_id": "github:Hawkar-usls",
            "repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
            "ref": "main",
            "created_at": "2026-08-31T08:00:00Z",
            "source_issue_id": 123456,
            "source_issue_number": 14,
            "max_tree_entries": 5000,
            "max_blob_files": 24,
            "max_total_blob_bytes": 750000,
        }

    def test_deterministic_packet(self):
        a = build_shadow_packet(self.request())
        b = build_shadow_packet(self.request())
        self.assertEqual(a, b)
        self.assertTrue(verify_shadow_packet(a))
        self.assertFalse(a["money_enabled"])
        self.assertFalse(a["purchase_grant"]["execution_authority_granted"])
        self.assertFalse(a["execute_repository_code"])

    def test_target_change_changes_identity(self):
        a = build_shadow_packet(self.request())
        other = self.request(); other["repository"] = "Hawkar-usls/Hawkar-usls"
        b = build_shadow_packet(other)
        self.assertNotEqual(a["service_request_hash"], b["service_request_hash"])
        self.assertNotEqual(a["packet_id"], b["packet_id"])

    def test_tamper_fails_verification(self):
        p = build_shadow_packet(self.request())
        p["execute_repository_code"] = True
        self.assertFalse(verify_shadow_packet(p))


if __name__ == "__main__":
    unittest.main()
