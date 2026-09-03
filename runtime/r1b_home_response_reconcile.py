#!/usr/bin/env python3
"""Verify and persist HOME -> JANUS MACHINE MARKET buyer-query responses.

The same return gate serves zero-price and paid settled buyer queries. A paid
response must already bind a settled purchase in the persistent commerce ledger
and is atomically indexed as the purchase's single execution identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from runtime.purchase_ledger import persist_paid_home_response

HOME_RESPONSE_SCHEMA = "janus.home.market_buyer_query_response.v1"
BUYER_RECEIPT_SCHEMA = "janus.machine_market.buyer_query_receipt.v1"
TERMINAL_RESPONSE_SCHEMA = "janus.terminal.response.v1"
MARKET_REPOSITORY = "Hawkar-usls/JANUS-MACHINE-MARKET"
HOME_REPOSITORY = "Hawkar-usls/Hawkar-usls"
ZERO_MODE = "ZERO_PRICE_SHADOW"
PAID_MODE = "PAID_SETTLED"


class HomeResponseError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise HomeResponseError(code)


def verify_home_response(response: dict[str, Any]) -> bool:
    if not isinstance(response, dict):
        return False
    outer = dict(response)
    claimed = str(outer.pop("home_response_hash", ""))
    if len(claimed) != 64 or digest(outer) != claimed:
        return False
    if outer.get("schema") != HOME_RESPONSE_SCHEMA:
        return False
    if outer.get("market_repository") != MARKET_REPOSITORY or outer.get("home_repository") != HOME_REPOSITORY:
        return False
    mode=outer.get("mode")
    if mode not in (ZERO_MODE,PAID_MODE):
        return False
    paid=mode==PAID_MODE
    if outer.get("money_enabled") is not paid:
        return False
    if outer.get("payment_required",False) is not paid or outer.get("production_purchase",False) is not paid:
        return False
    if outer.get("same_resident_required") is not True or outer.get("exact_retry_is_second_cognition") is not False:
        return False
    for field in ("execution_authority_granted", "command_authority_granted", "external_effect_authorized"):
        if outer.get(field) is not False:
            return False

    receipt = outer.get("buyer_query_receipt")
    terminal = outer.get("terminal_response")
    source = outer.get("source_packet_binding")
    route = outer.get("return_route")
    if not all(isinstance(x, dict) for x in (receipt, terminal, source, route)):
        return False
    if receipt.get("schema") != BUYER_RECEIPT_SCHEMA or terminal.get("schema") != TERMINAL_RESPONSE_SCHEMA:
        return False
    if route.get("repository") != MARKET_REPOSITORY:
        return False
    if receipt.get("purchase_id") != outer.get("purchase_id"):
        return False
    if receipt.get("purchase_grant_hash") != outer.get("purchase_grant_hash"):
        return False
    if receipt.get("query_id") != outer.get("query_id") or receipt.get("query_hash") != outer.get("query_hash"):
        return False
    if receipt.get("execution_identity") != terminal.get("response_id") or outer.get("terminal_response_id") != terminal.get("response_id"):
        return False
    if receipt.get("resident_uuid") != terminal.get("resident_uuid"):
        return False
    if receipt.get("model_digest") != terminal.get("model_digest"):
        return False
    if receipt.get("file_fabric_digest") != terminal.get("file_fabric_digest"):
        return False
    if receipt.get("turn_id") != terminal.get("turn_id"):
        return False
    if receipt.get("response_hash") != terminal.get("response_hash") or outer.get("terminal_response_hash") != terminal.get("response_hash"):
        return False
    if receipt.get("response_text") != terminal.get("response_text"):
        return False
    if receipt.get("hrain_context_receipt_hash") != terminal.get("hrain_context_receipt_hash"):
        return False
    if receipt.get("hrain_context_hash") != terminal.get("hrain_context_hash"):
        return False
    if receipt.get("memory_source_commit") != terminal.get("memory_source_commit"):
        return False
    if receipt.get("execution_authority_granted") is not False or receipt.get("external_effect_authorized") is not False:
        return False
    if receipt.get("scientific_evidence_authority_granted") is not False or receipt.get("world_truth_authority_granted") is not False:
        return False
    if paid:
        payment_ref=str(outer.get("payment_reference") or "").lower()
        if not payment_ref or str(receipt.get("payment_reference") or "").lower()!=payment_ref:
            return False
        if receipt.get("billable_execution_delta") not in (0,1):
            return False
    else:
        if outer.get("payment_reference") is not None or receipt.get("payment_reference") is not None:
            return False
        if receipt.get("billable_execution_delta") != 0:
            return False
    if terminal.get("command_authority_granted") is not False or terminal.get("external_effect_authorized") is not False:
        return False
    if terminal.get("physical_runtime_effect_authorized") is not False:
        return False
    if terminal.get("persistent_identity_verified") is not True or terminal.get("instantiated_model_verified") is not True:
        return False
    if terminal.get("hrain_context_bound") is not True:
        return False

    t = dict(terminal)
    terminal_hash = str(t.pop("response_hash", ""))
    if len(terminal_hash) != 64 or digest(t) != terminal_hash:
        return False
    if outer.get("terminal_message_hash") != terminal.get("request_message_hash"):
        return False
    if source.get("market_packet_hash") is None or source.get("pull_receipt_hash") is None:
        return False
    if source.get("transport") != "PHYSARIUS_CREDENTIALLESS_PULL":
        return False
    return True


def reconcile_response(*, response_path: Path, state_root: Path) -> dict[str, Any]:
    response = json.loads(response_path.read_text(encoding="utf-8"))
    require(verify_home_response(response), "R1B_HOME_RESPONSE_INVALID")
    qid = str(response["query_id"])
    purchase_id = str(response["purchase_id"])
    paid=response["mode"]==PAID_MODE
    receipts = state_root / "state/r1b-buyer-query/receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    target = receipts / f"{qid}.json"
    new = False
    if target.exists():
        require(target.read_bytes() == response_path.read_bytes(), "R1B_MARKET_RECEIPT_CREATE_ONLY_CONFLICT")
    else:
        shutil.copyfile(response_path, target)
        new = True

    commerce_ledger=None
    if paid:
        commerce_ledger=persist_paid_home_response(state_root,response)

    head = {
        "schema": "janus.machine_market.r1b_buyer_query_head.v1",
        "status": "R1B_PAID_HOME_RESPONSE_RECONCILED" if paid else "R1B_ZERO_PRICE_HOME_RESPONSE_RECONCILED",
        "mode":response["mode"],
        "query_id": qid,
        "query_hash": response["query_hash"],
        "purchase_id": purchase_id,
        "purchase_grant_hash": response["purchase_grant_hash"],
        "payment_reference":response.get("payment_reference"),
        "resident_uuid": response["buyer_query_receipt"]["resident_uuid"],
        "model_digest": response["buyer_query_receipt"]["model_digest"],
        "file_fabric_digest": response["buyer_query_receipt"]["file_fabric_digest"],
        "execution_identity": response["buyer_query_receipt"]["execution_identity"],
        "response_hash": response["buyer_query_receipt"]["response_hash"],
        "home_response_hash": response["home_response_hash"],
        "money_enabled": paid,
        "production_purchase": paid,
        "external_effect_authorized": False,
        "foreign_buyer_witness": False,
    }
    head_path = state_root / "state/r1b-buyer-query/HEAD.json"
    head_path.parent.mkdir(parents=True, exist_ok=True)
    head_path.write_text(json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema": "janus.machine_market.r1b_reconcile_result.v1",
        "mode":response["mode"],
        "query_id": qid,
        "purchase_id": purchase_id,
        "payment_reference":response.get("payment_reference"),
        "resident_uuid": head["resident_uuid"],
        "execution_identity": head["execution_identity"],
        "response_hash": head["response_hash"],
        "home_response_hash": head["home_response_hash"],
        "source_issue_number": (response.get("return_route") or {}).get("source_issue_number"),
        "new_receipt": new,
        "money_enabled": paid,
        "production_purchase":paid,
        "commerce_execution_ledger":commerce_ledger,
        "foreign_buyer_witness": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and persist one HOME -> JANUS Machine Market R1B response")
    parser.add_argument("--response", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--result-out", required=True)
    args = parser.parse_args()
    result = reconcile_response(response_path=Path(args.response), state_root=Path(args.state_root))
    Path(args.result_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.result_out).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
