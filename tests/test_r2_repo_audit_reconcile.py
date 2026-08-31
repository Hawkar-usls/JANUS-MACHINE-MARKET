from __future__ import annotations

import copy
import unittest

from runtime.r2_repo_audit_reconcile import (
    build_market_receipt,
    digest,
    is_safe_identifier,
    verify_home_response,
    verify_packet,
)
from runtime.r2_repo_audit_shadow import build_shadow_packet


class RepoAuditReconcileTest(unittest.TestCase):
    def packet(self):
        return build_shadow_packet(
            {
                "buyer_actor_id": "github:Hawkar-usls",
                "repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
                "ref": "main",
                "created_at": "2026-08-31T08:00:00Z",
                "source_issue_id": 123,
                "source_issue_number": 14,
            }
        )

    def response(self, p):
        request = p["service_request"]
        audit = {
            "schema": "janus.market_service.repo_audit_result.v1",
            "status": "BOUNDED_REPOSITORY_AUDIT_COMPLETE",
            "request_id": request["request_id"],
            "request_hash": request["request_hash"],
            "sku": "JANUS.REPO_AUDIT",
            "target": {
                "repository": request["repository"],
                "requested_ref": request["ref"],
                "resolved_commit_sha": "a" * 40,
                "tree_sha": "b" * 40,
            },
            "bounds": {
                "observed_tree_entries": 42,
            },
            "architecture_map": {
                "has_tests": True,
                "has_ci": True,
            },
            "license_observations": {
                "license_file_observed": True,
            },
            "risk_register": [
                {"code": "EXAMPLE_RISK", "severity": "LOW", "scope": "test"},
            ],
            "authority": {
                "read_only": True,
                "repository_write": False,
                "repository_code_executed": False,
                "command_authority_granted": False,
                "claim_authority_granted": False,
                "scientific_evidence_authority_granted": False,
                "world_truth_authority_granted": False,
                "external_effect_authorized": False,
            },
        }
        audit["result_hash"] = digest(audit)
        body = {
            "schema": "janus.machine_market.home_repo_audit_response.v1",
            "sku": "JANUS.REPO_AUDIT",
            "packet_id": p["packet_id"],
            "packet_hash": p["packet_hash"],
            "purchase_id": p["purchase_grant"]["purchase_id"],
            "purchase_grant_hash": p["purchase_grant_hash"],
            "service_request_id": request["request_id"],
            "service_request_hash": request["request_hash"],
            "commerce_mode": p["commerce_mode"],
            "money_enabled": p["money_enabled"],
            "payment_reference": p["payment_reference"],
            "resident_uuid": "resident",
            "model_digest": "c" * 64,
            "file_fabric_digest": "d" * 64,
            "runtime_receipt_hash": "e" * 64,
            "home_service_receipt_hash": "f" * 64,
            "audit_result_hash": audit["result_hash"],
            "audit_result": audit,
            "same_resident_uuid": True,
            "return_home_verified": True,
            "replayed": False,
            "source_binding": {"transport": "PHYSARIUS_CREDENTIALLESS_PULL"},
            "command_authority_granted": False,
            "external_effect_authorized": False,
            "repository_write_authorized": False,
            "repository_code_executed": False,
            "security_certification_granted": False,
            "legal_opinion_granted": False,
            "laws": [],
        }
        body["home_response_hash"] = digest(body)
        return body

    @staticmethod
    def reseal_response(response):
        response["audit_result"]["result_hash"] = digest(
            {k: v for k, v in response["audit_result"].items() if k != "result_hash"}
        )
        response["audit_result_hash"] = response["audit_result"]["result_hash"]
        response["home_response_hash"] = digest(
            {k: v for k, v in response.items() if k != "home_response_hash"}
        )

    def test_valid_response_closes_service_debt(self):
        p = self.packet()
        r = self.response(p)
        self.assertTrue(verify_packet(p))
        self.assertTrue(verify_home_response(r, packet=p))
        rid = p["service_request"]["request_id"]
        receipt = build_market_receipt(
            r,
            packet=p,
            home_source_commit="1" * 40,
            home_response_path=f".janus/market-service-responses/{rid}.repo-audit-result.json",
            home_response_blob_sha="2" * 40,
        )
        self.assertTrue(receipt["verified_buyer_delivery"])
        self.assertTrue(receipt["service_debt_closed"])
        self.assertFalse(receipt["repository_code_executed"])

    def test_target_rebinding_fails(self):
        p = self.packet()
        r = self.response(p)
        r["audit_result"]["target"]["repository"] = "other/repo"
        self.reseal_response(r)
        self.assertFalse(verify_home_response(r, packet=p))

    def test_effect_authority_fails(self):
        p = self.packet()
        r = self.response(p)
        r["external_effect_authorized"] = True
        r["home_response_hash"] = digest({k: v for k, v in r.items() if k != "home_response_hash"})
        self.assertFalse(verify_home_response(r, packet=p))

    def test_nested_result_tamper_with_resealed_outer_response_fails(self):
        p = self.packet()
        r = self.response(p)
        r["audit_result"]["architecture_map"]["has_tests"] = False
        # Deliberately do not update result_hash; only reseal the outer envelope.
        r["home_response_hash"] = digest({k: v for k, v in r.items() if k != "home_response_hash"})
        self.assertFalse(verify_home_response(r, packet=p))

    def test_result_return_fields_are_required_before_delivery(self):
        p = self.packet()
        for field in ("architecture_map", "license_observations", "risk_register", "bounds"):
            with self.subTest(field=field):
                r = self.response(p)
                del r["audit_result"][field]
                self.reseal_response(r)
                self.assertFalse(verify_home_response(r, packet=p))

    def test_result_return_field_types_are_fail_closed(self):
        p = self.packet()
        cases = [
            ("architecture_map", {"has_tests": "yes", "has_ci": True}),
            ("license_observations", {"license_file_observed": "yes"}),
            ("bounds", {"observed_tree_entries": True}),
            ("risk_register", [{"code": "BAD\nMARKER"}]),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                r = self.response(p)
                r["audit_result"][field] = value
                self.reseal_response(r)
                self.assertFalse(verify_home_response(r, packet=p))

    def test_unsafe_request_ids_fail_before_path_use(self):
        self.assertTrue(is_safe_identifier("ra-shadow-" + "a" * 48))
        for unsafe in (
            "../escape",
            "/tmp/escape",
            "x'; touch PWNED; #",
            "$(touch PWNED)",
            "`touch PWNED`",
            "line\nbreak",
            "a/b",
            "a" * 97,
        ):
            with self.subTest(unsafe=unsafe):
                self.assertFalse(is_safe_identifier(unsafe))
                p = copy.deepcopy(self.packet())
                p["service_request"]["request_id"] = unsafe
                p["service_request"]["request_hash"] = digest(
                    {k: v for k, v in p["service_request"].items() if k != "request_hash"}
                )
                p["service_request_hash"] = p["service_request"]["request_hash"]
                p["packet_hash"] = digest({k: v for k, v in p.items() if k != "packet_hash"})
                self.assertFalse(verify_packet(p))

    def test_receipt_rejects_wrong_response_path_binding(self):
        p = self.packet()
        r = self.response(p)
        with self.assertRaisesRegex(ValueError, "REPO_AUDIT_HOME_RESPONSE_PATH_BINDING_INVALID"):
            build_market_receipt(
                r,
                packet=p,
                home_source_commit="1" * 40,
                home_response_path=".janus/market-service-responses/other.repo-audit-result.json",
                home_response_blob_sha="2" * 40,
            )


if __name__ == "__main__":
    unittest.main()
