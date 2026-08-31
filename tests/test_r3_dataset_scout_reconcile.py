from __future__ import annotations

import copy
import unittest

from runtime.r3_dataset_scout_reconcile import build_market_receipt, digest, verify_home_response
from runtime.r3_dataset_scout_shadow import build_shadow_packet


class DatasetScoutReconcileTests(unittest.TestCase):
    def packet(self):
        return build_shadow_packet({
            "buyer_actor_id": "github:Hawkar-usls",
            "query": "climate",
            "domain": "earth science",
            "date_range": None,
            "license_preferences": [],
            "format_preferences": [],
            "max_results": 5,
            "max_catalogs": 2,
            "per_catalog_timeout_seconds": 8,
            "created_at": "2026-08-31T15:00:00Z",
            "source_issue_id": 123456,
            "source_issue_number": 16,
        })

    def response(self, packet):
        request = packet["service_request"]
        result = {
            "schema": "janus.market_service.dataset_scout_result.v1",
            "status": "BOUNDED_DATASET_SCOUT_COMPLETE",
            "request_id": request["request_id"],
            "request_hash": request["request_hash"],
            "query": request["query"],
            "domain": request["domain"],
            "dataset_manifest": [{"catalog": "ZENODO", "dataset_id": "1", "title": "Climate", "source_url": "https://zenodo.org/records/1", "license_observation": "cc-by", "formats": ["csv"]}],
            "source_urls": ["https://zenodo.org/records/1"],
            "license_observations": [{"source_url": "https://zenodo.org/records/1", "observed": "cc-by", "authoritative_license_determination": False}],
            "deduplication_notes": {"key": "source_url", "duplicates_removed": 0},
            "provenance": {"catalogs_attempted": ["ZENODO"], "catalogs_succeeded": ["ZENODO"], "catalog_failures": [], "metadata_only": True},
            "authority": {"read_only": True, "dataset_payload_downloaded": False, "redistribution_authority_granted": False, "license_authority_granted": False, "command_authority_granted": False, "external_effect_authorized": False},
        }
        result["result_hash"] = digest(result)
        response = {
            "schema": "janus.machine_market.home_dataset_scout_response.v1",
            "sku": "JANUS.DATASET_SCOUT",
            "packet_id": packet["packet_id"],
            "packet_hash": packet["packet_hash"],
            "purchase_id": packet["purchase_grant"]["purchase_id"],
            "purchase_grant_hash": packet["purchase_grant_hash"],
            "service_request_id": request["request_id"],
            "service_request_hash": request["request_hash"],
            "commerce_mode": packet["commerce_mode"],
            "money_enabled": False,
            "payment_reference": None,
            "resident_uuid": "75e514ab-be76-42c8-bcb3-fc9670164f96",
            "model_digest": "1" * 64,
            "file_fabric_digest": "2" * 64,
            "home_service_receipt_hash": "3" * 64,
            "dataset_scout_result_hash": result["result_hash"],
            "dataset_scout_result": result,
            "same_resident_uuid": True,
            "return_home_verified": True,
            "command_authority_granted": False,
            "external_effect_authorized": False,
            "dataset_payload_downloaded": False,
            "redistribution_authority_granted": False,
            "license_authority_granted": False,
        }
        response["home_response_hash"] = digest(response)
        return response

    def test_verified_delivery_receipt(self):
        packet = self.packet(); response = self.response(packet)
        self.assertTrue(verify_home_response(response, packet=packet))
        receipt = build_market_receipt(response, packet=packet, home_source_commit="a" * 40, home_response_path="x.json", home_response_blob_sha="b" * 40)
        self.assertTrue(receipt["verified_buyer_delivery"])
        self.assertTrue(receipt["service_debt_closed"])
        self.assertEqual(receipt["candidate_count"], 1)
        self.assertFalse(receipt["redistribution_authority_granted"])

    def test_payload_authority_tamper_fails(self):
        packet = self.packet(); response = self.response(packet)
        bad = copy.deepcopy(response); bad["dataset_payload_downloaded"] = True
        self.assertFalse(verify_home_response(bad, packet=packet))


if __name__ == "__main__":
    unittest.main()
