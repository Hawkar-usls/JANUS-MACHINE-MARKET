from __future__ import annotations

import copy
import unittest

from runtime.r3_dataset_scout_shadow import build_shadow_packet, verify_shadow_packet


class DatasetScoutShadowTests(unittest.TestCase):
    def request(self):
        return {
            "buyer_actor_id": "github:Hawkar-usls",
            "query": "climate",
            "domain": "earth science",
            "date_range": None,
            "license_preferences": ["cc-by"],
            "format_preferences": ["csv"],
            "max_results": 5,
            "max_catalogs": 2,
            "per_catalog_timeout_seconds": 8,
            "created_at": "2026-08-31T15:00:00Z",
            "source_issue_id": 123456,
            "source_issue_number": 16,
        }

    def test_packet_is_deterministic_and_valid(self):
        a = build_shadow_packet(self.request())
        b = build_shadow_packet(self.request())
        self.assertEqual(a, b)
        self.assertTrue(verify_shadow_packet(a))
        self.assertEqual(a["sku"], "JANUS.DATASET_SCOUT")
        self.assertFalse(a["money_enabled"])
        self.assertFalse(a["dataset_payload_download_authorized"])
        self.assertFalse(a["redistribution_authority_granted"])
        self.assertFalse(a["purchase_grant"]["execution_authority_granted"])

    def test_authority_tamper_fails(self):
        packet = build_shadow_packet(self.request())
        bad = copy.deepcopy(packet)
        bad["redistribution_authority_granted"] = True
        self.assertFalse(verify_shadow_packet(bad))

    def test_query_changes_identity(self):
        a = build_shadow_packet(self.request())
        req = self.request(); req["query"] = "ocean temperature"
        b = build_shadow_packet(req)
        self.assertNotEqual(a["service_request"]["request_id"], b["service_request"]["request_id"])


if __name__ == "__main__":
    unittest.main()
