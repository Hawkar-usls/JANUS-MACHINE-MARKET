from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime.r2_repo_audit_reconcile import (
    build_market_receipt,
    digest,
    is_safe_identifier,
    prevalidate_home_response_identity,
    verify_home_response,
    verify_packet,
)
from runtime.r2_repo_audit_selector import select_verified_response
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
            "bounds": {"observed_tree_entries": 42},
            "architecture_map": {"has_tests": True, "has_ci": True},
            "license_observations": {"license_file_observed": True},
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

    @staticmethod
    def write_json(path: Path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

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

    def test_schema_and_identity_prevalidation_precedes_path_use(self):
        p = self.packet()
        r = self.response(p)
        self.assertEqual(prevalidate_home_response_identity(r), p["service_request"]["request_id"])
        for mutation in (
            {"schema": "wrong.schema"},
            {"sku": "OTHER"},
            {"service_request_id": "../escape"},
            {"service_request_hash": "not-a-hash"},
            {"packet_hash": "not-a-hash"},
        ):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(r)
                bad.update(mutation)
                self.assertIsNone(prevalidate_home_response_identity(bad))

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

    def test_selector_quarantines_invalid_candidate_then_selects_valid(self):
        p = self.packet()
        good = self.response(p)
        bad = copy.deepcopy(good)
        bad["audit_result"]["target"]["repository"] = "attacker/repo"
        self.reseal_response(bad)
        rid = p["service_request"]["request_id"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            outbox = root / "outbox"
            receipts = root / "receipts"
            quarantine = root / "quarantine"
            self.write_json(home / "00-invalid.repo-audit-result.json", bad)
            self.write_json(home / "01-valid.repo-audit-result.json", good)
            self.write_json(outbox / f"{rid}.repo-audit.packet.json", p)
            result = select_verified_response(
                home_dir=home,
                outbox_dir=outbox,
                receipts_dir=receipts,
                quarantine_dir=quarantine,
            )
            self.assertTrue(result["found"])
            self.assertEqual(result["request_id"], rid)
            self.assertEqual(len(result["quarantined"]), 1)
            records = list(quarantine.glob("*.json"))
            self.assertEqual(len(records), 1)
            record = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertEqual(record["reason"], "HOME_RESPONSE_VERIFICATION_FAILED")
            self.assertFalse(record["delivery_receipt_written"])

    def test_selector_quarantines_malformed_and_unsafe_identity_without_blocking_valid(self):
        p = self.packet()
        good = self.response(p)
        unsafe = copy.deepcopy(good)
        unsafe["service_request_id"] = "x'; touch PWNED; #"
        unsafe["home_response_hash"] = digest({k: v for k, v in unsafe.items() if k != "home_response_hash"})
        rid = p["service_request"]["request_id"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            outbox = root / "outbox"
            receipts = root / "receipts"
            quarantine = root / "quarantine"
            home.mkdir(parents=True)
            (home / "00-malformed.repo-audit-result.json").write_text("{not json\n", encoding="utf-8")
            self.write_json(home / "01-unsafe.repo-audit-result.json", unsafe)
            self.write_json(home / "02-valid.repo-audit-result.json", good)
            self.write_json(outbox / f"{rid}.repo-audit.packet.json", p)
            result = select_verified_response(
                home_dir=home,
                outbox_dir=outbox,
                receipts_dir=receipts,
                quarantine_dir=quarantine,
            )
            self.assertTrue(result["found"])
            self.assertEqual(result["request_id"], rid)
            self.assertEqual(len(result["quarantined"]), 2)
            reasons = {
                json.loads(path.read_text(encoding="utf-8"))["reason"]
                for path in quarantine.glob("*.json")
            }
            self.assertEqual(reasons, {"MALFORMED_JSON", "SCHEMA_OR_IDENTITY_PREVALIDATION_FAILED"})


if __name__ == "__main__":
    unittest.main()
