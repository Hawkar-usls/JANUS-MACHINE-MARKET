from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.r2_repo_audit_reconcile import (
    build_market_receipt,
    build_result_comment,
    digest,
    expected_home_response_path,
    require_request_id,
    select_oldest_verified_response,
    verify_home_response,
    verify_market_receipt,
    verify_packet,
)
from runtime.r2_repo_audit_shadow import build_shadow_packet


class RepoAuditReconcileTest(unittest.TestCase):
    def packet(self, source_issue_id: int = 123, source_issue_number: int = 14):
        return build_shadow_packet(
            {
                "buyer_actor_id": "github:Hawkar-usls",
                "repository": "Hawkar-usls/JANUS-MACHINE-MARKET",
                "ref": "main",
                "created_at": "2026-08-31T08:00:00Z",
                "source_issue_id": source_issue_id,
                "source_issue_number": source_issue_number,
            }
        )

    def reseal(self, response):
        audit = response["audit_result"]
        audit["result_hash"] = digest({key: value for key, value in audit.items() if key != "result_hash"})
        response["audit_result_hash"] = audit["result_hash"]
        response["home_response_hash"] = digest(
            {key: value for key, value in response.items() if key != "home_response_hash"}
        )
        return response

    def response(self, packet):
        request = packet["service_request"]
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
            "bounds": {
                "observed_tree_entries": 90,
            },
            "architecture_map": {
                "has_tests": True,
                "has_ci": True,
            },
            "license_observations": {
                "license_file_observed": True,
            },
            "risk_register": [],
        }
        body = {
            "schema": "janus.machine_market.home_repo_audit_response.v1",
            "sku": "JANUS.REPO_AUDIT",
            "packet_id": packet["packet_id"],
            "packet_hash": packet["packet_hash"],
            "purchase_id": packet["purchase_grant"]["purchase_id"],
            "purchase_grant_hash": packet["purchase_grant_hash"],
            "service_request_id": request["request_id"],
            "service_request_hash": request["request_hash"],
            "commerce_mode": packet["commerce_mode"],
            "money_enabled": packet["money_enabled"],
            "payment_reference": packet["payment_reference"],
            "resident_uuid": "75e514ab-be76-42c8-bcb3-fc9670164f96",
            "model_digest": "c" * 64,
            "file_fabric_digest": "d" * 64,
            "runtime_receipt_hash": "e" * 64,
            "home_service_receipt_hash": "f" * 64,
            "audit_result_hash": "",
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
        return self.reseal(body)

    def write_packet(self, root: Path, packet):
        rid = packet["service_request"]["request_id"]
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{rid}.repo-audit.packet.json").write_text(
            json.dumps(packet, sort_keys=True), encoding="utf-8"
        )

    def write_response(self, root: Path, response, filename: str | None = None):
        rid = response.get("service_request_id", "invalid")
        root.mkdir(parents=True, exist_ok=True)
        target = root / (filename or f"{rid}.repo-audit-result.json")
        target.write_text(json.dumps(response, sort_keys=True), encoding="utf-8")

    def select(self, root: Path, home_source_commit: str = "1" * 40):
        return select_oldest_verified_response(
            home_response_dir=root / "home",
            outbox_dir=root / "outbox",
            receipts_dir=root / "state" / "receipts",
            quarantine_dir=root / "state" / "quarantine",
            stage_dir=root / "stage",
            home_source_commit=home_source_commit,
        )

    def test_valid_response_closes_service_debt(self):
        packet = self.packet()
        response = self.response(packet)
        self.assertTrue(verify_packet(packet))
        self.assertTrue(verify_home_response(response, packet=packet))
        receipt = build_market_receipt(
            response,
            packet=packet,
            home_source_commit="1" * 40,
            home_response_path=expected_home_response_path(response["service_request_id"]),
            home_response_blob_sha="2" * 40,
        )
        self.assertTrue(receipt["verified_buyer_delivery"])
        self.assertTrue(receipt["service_debt_closed"])
        self.assertTrue(receipt["result_return_fields_validated"])
        self.assertTrue(receipt["result_return_ready"])
        self.assertTrue(verify_market_receipt(receipt, response=response, packet=packet))
        comment = build_result_comment(response, packet=packet)
        self.assertIn("REPO_AUDIT_RETURNED:", comment)
        self.assertIn("observed_tree_entries: `90`", comment)

    def test_target_rebinding_fails(self):
        packet = self.packet()
        response = self.response(packet)
        response["audit_result"]["target"]["repository"] = "other/repo"
        self.reseal(response)
        self.assertFalse(verify_home_response(response, packet=packet))

    def test_effect_authority_fails(self):
        packet = self.packet()
        response = self.response(packet)
        response["external_effect_authorized"] = True
        self.reseal(response)
        self.assertFalse(verify_home_response(response, packet=packet))

    def test_malformed_nested_packet_fails_closed(self):
        packet = self.packet()
        packet["service_request"] = "not-an-object"
        packet["packet_hash"] = digest({key: value for key, value in packet.items() if key != "packet_hash"})
        self.assertFalse(verify_packet(packet))

    def test_all_result_return_fields_are_mandatory_before_receipt(self):
        cases = (
            "bounds",
            "architecture_map",
            "license_observations",
            "risk_register",
        )
        for field in cases:
            with self.subTest(field=field):
                packet = self.packet()
                response = self.response(packet)
                response["audit_result"].pop(field)
                self.reseal(response)
                self.assertFalse(verify_home_response(response, packet=packet))
                with self.assertRaisesRegex(ValueError, "REPO_AUDIT_HOME_RESPONSE_INVALID"):
                    build_market_receipt(
                        response,
                        packet=packet,
                        home_source_commit="1" * 40,
                        home_response_path=expected_home_response_path(
                            packet["service_request"]["request_id"]
                        ),
                        home_response_blob_sha="2" * 40,
                    )

    def test_result_return_nested_types_and_codes_fail_closed(self):
        packet = self.packet()
        mutations = (
            ("has_tests", lambda response: response["audit_result"]["architecture_map"].update(has_tests="yes")),
            (
                "license_file_observed",
                lambda response: response["audit_result"]["license_observations"].update(
                    license_file_observed=1
                ),
            ),
            (
                "risk_code",
                lambda response: response["audit_result"].update(
                    risk_register=[{"code": "BAD`code"}]
                ),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                response = self.response(packet)
                mutate(response)
                self.reseal(response)
                self.assertFalse(verify_home_response(response, packet=packet))

    def test_receipt_rejects_noncanonical_response_path(self):
        packet = self.packet()
        response = self.response(packet)
        with self.assertRaisesRegex(ValueError, "REPO_AUDIT_HOME_RESPONSE_PATH_INVALID"):
            build_market_receipt(
                response,
                packet=packet,
                home_source_commit="1" * 40,
                home_response_path="../../escape.json",
                home_response_blob_sha="2" * 40,
            )

    def test_untrusted_request_id_is_quarantined_without_shell_or_path_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "PWNED"
            packet = self.packet()
            response = self.response(packet)
            malicious = f"x'; touch {sentinel}; #"
            response["service_request_id"] = malicious
            response["audit_result"]["request_id"] = malicious
            self.reseal(response)
            self.write_response(
                root / "home",
                response,
                filename="000-malicious.repo-audit-result.json",
            )
            result = self.select(root)
            self.assertFalse(result["found"])
            self.assertFalse(sentinel.exists())
            records = list((root / "state" / "quarantine").glob("*.json"))
            self.assertEqual(len(records), 1)
            self.assertRegex(records[0].name, r"^raq-[0-9a-f]{48}\.json$")
            record = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertIn("SERVICE_REQUEST_ID_FORMAT_INVALID", record["reason_codes"])
            self.assertFalse(record["delivery_receipt_created"])
            self.assertFalse((root / "escape.json").exists())
            with self.assertRaisesRegex(ValueError, "REQUEST_ID_FORMAT_INVALID"):
                require_request_id(malicious)

    def test_invalid_response_is_quarantined_and_does_not_block_next_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packets = [self.packet(1001, 21), self.packet(1002, 22)]
            packets.sort(key=lambda item: item["service_request"]["request_id"])
            invalid_packet, valid_packet = packets
            invalid_response = self.response(invalid_packet)
            invalid_response["audit_result"].pop("architecture_map")
            self.reseal(invalid_response)
            valid_response = self.response(valid_packet)
            for packet in packets:
                self.write_packet(root / "outbox", packet)
            self.write_response(root / "home", invalid_response)
            self.write_response(root / "home", valid_response)

            result = self.select(root)
            self.assertTrue(result["found"])
            self.assertEqual(
                result["request_id"], valid_packet["service_request"]["request_id"]
            )
            self.assertEqual(result["quarantined_count"], 1)
            self.assertEqual(result["quarantine_created_count"], 1)
            selected = json.loads((root / "stage" / "home-response.json").read_text())
            self.assertEqual(
                selected["service_request_id"],
                valid_packet["service_request"]["request_id"],
            )
            record_path = next((root / "state" / "quarantine").glob("*.json"))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertIn(
                "RESULT_RETURN_ARCHITECTURE_MAP_REQUIRED", record["reason_codes"]
            )

    def test_parseable_semantic_invalid_response_is_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self.packet()
            response = self.response(packet)
            response["audit_result"]["target"]["tree_sha"] = "not-a-git-sha"
            self.reseal(response)
            self.write_packet(root / "outbox", packet)
            self.write_response(root / "home", response)
            result = self.select(root)
            self.assertFalse(result["found"])
            record_path = next((root / "state" / "quarantine").glob("*.json"))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertIn("HOME_RESPONSE_SEMANTIC_INVALID", record["reason_codes"])

    def test_exact_quarantine_retry_is_create_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home").mkdir(parents=True)
            (root / "home" / "broken.repo-audit-result.json").write_text(
                "{not-json", encoding="utf-8"
            )
            first = self.select(root)
            second = self.select(root)
            self.assertEqual(first["quarantine_created_count"], 1)
            self.assertEqual(second["quarantine_created_count"], 0)
            self.assertEqual(
                len(list((root / "state" / "quarantine").glob("*.json"))), 1
            )

    def test_workflow_keeps_request_id_out_of_generated_shell_source(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "r2-repo-audit-reconcile.yml"
        ).read_text(encoding="utf-8")
        lines = workflow.splitlines()
        run_blocks = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.lstrip().startswith("run: |"):
                indent = len(line) - len(line.lstrip())
                block = []
                index += 1
                while index < len(lines):
                    candidate = lines[index]
                    if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= indent:
                        break
                    block.append(candidate)
                    index += 1
                run_blocks.append("\n".join(block))
                continue
            index += 1
        shell_source = "\n".join(run_blocks)
        expression = "${{ steps.select.outputs.request_id }}"
        self.assertNotIn(expression, shell_source)
        self.assertIn(f"REQUEST_ID: {expression}", workflow)
        self.assertIn("group: janus-machine-market-state-writer", workflow)
        self.assertNotIn("group: janus-machine-market-service-reconcile", workflow)


if __name__ == "__main__":
    unittest.main()
