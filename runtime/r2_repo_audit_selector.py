#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from runtime.r2_repo_audit_reconcile import prevalidate_home_response_identity, verify_home_response


def _write_quarantine(path: Path, *, quarantine_dir: Path, reason: str, observed_id: Any = "") -> Path:
    raw = path.read_bytes()
    source_sha = hashlib.sha256(raw).hexdigest()
    record = {
        "schema": "janus.machine_market.repo_audit_invalid_home_response.v1",
        "source_filename": path.name,
        "source_sha256": source_sha,
        "reason": reason,
        "observed_service_request_id": str(observed_id)[:256],
        "selected_for_delivery": False,
        "delivery_receipt_written": False,
    }
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    target = quarantine_dir / f"{source_sha}.json"
    encoded = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("REPO_AUDIT_QUARANTINE_HASH_COLLISION")
    target.write_text(encoded, encoding="utf-8")
    return target


def select_verified_response(
    *,
    home_dir: Path,
    outbox_dir: Path,
    receipts_dir: Path,
    quarantine_dir: Path,
) -> dict[str, Any]:
    """Select the first fully verified unreconciled response, never merely the first parseable file."""
    quarantined: list[str] = []
    if not home_dir.is_dir():
        return {"found": False, "request_id": "", "quarantined": quarantined}

    for path in sorted(home_dir.glob("*.repo-audit-result.json")):
        try:
            response = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            quarantined.append(str(_write_quarantine(path, quarantine_dir=quarantine_dir, reason="MALFORMED_JSON")))
            continue

        request_id = prevalidate_home_response_identity(response)
        if request_id is None:
            quarantined.append(
                str(
                    _write_quarantine(
                        path,
                        quarantine_dir=quarantine_dir,
                        reason="SCHEMA_OR_IDENTITY_PREVALIDATION_FAILED",
                        observed_id=response.get("service_request_id") if isinstance(response, dict) else "",
                    )
                )
            )
            continue

        # Identity-derived paths are constructed only after schema + filename-safe ID prevalidation.
        if (receipts_dir / f"{request_id}.json").exists():
            continue
        packet_path = outbox_dir / f"{request_id}.repo-audit.packet.json"
        if not packet_path.is_file():
            quarantined.append(
                str(
                    _write_quarantine(
                        path,
                        quarantine_dir=quarantine_dir,
                        reason="MATCHING_PACKET_MISSING",
                        observed_id=request_id,
                    )
                )
            )
            continue
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except Exception:
            quarantined.append(
                str(
                    _write_quarantine(
                        path,
                        quarantine_dir=quarantine_dir,
                        reason="MATCHING_PACKET_MALFORMED",
                        observed_id=request_id,
                    )
                )
            )
            continue
        if not verify_home_response(response, packet=packet):
            quarantined.append(
                str(
                    _write_quarantine(
                        path,
                        quarantine_dir=quarantine_dir,
                        reason="HOME_RESPONSE_VERIFICATION_FAILED",
                        observed_id=request_id,
                    )
                )
            )
            continue
        return {
            "found": True,
            "request_id": request_id,
            "response": response,
            "packet": packet,
            "source_path": path,
            "quarantined": quarantined,
        }

    return {"found": False, "request_id": "", "quarantined": quarantined}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home-dir", required=True)
    parser.add_argument("--outbox-dir", required=True)
    parser.add_argument("--receipts-dir", required=True)
    parser.add_argument("--runtime-dir", required=True)
    args = parser.parse_args()

    runtime_dir = Path(args.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    result = select_verified_response(
        home_dir=Path(args.home_dir),
        outbox_dir=Path(args.outbox_dir),
        receipts_dir=Path(args.receipts_dir),
        quarantine_dir=runtime_dir / "quarantine",
    )
    print("quarantine_count=" + str(len(result["quarantined"])))
    if not result["found"]:
        print("found=false")
        print("request_id=")
        return 0

    request_id = result["request_id"]
    (runtime_dir / "home-response.json").write_text(
        json.dumps(result["response"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (runtime_dir / "packet.json").write_text(
        json.dumps(result["packet"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (runtime_dir / "selected-response-path.txt").write_text(
        f".janus/market-service-responses/{request_id}.repo-audit-result.json\n", encoding="utf-8"
    )
    print("found=true")
    print("request_id=" + request_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
