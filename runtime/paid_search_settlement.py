#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime.commerce_authority import CommerceInvalid, receipt_payment_reference, verify_payment_receipt
from runtime.ethereum_usdt_observer import JsonRpc, observe_transaction
from runtime.paid_search_checkout import settle_invoice
from runtime.paid_search_packet import build_paid_home_packet, verify_paid_home_packet
from runtime.purchase_ledger import consumed_payment_references, payment_key, persist_purchase


def _load(path: str | Path) -> dict[str,Any]:
    value=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise CommerceInvalid(f"expected object: {path}")
    return value


def recover_purchase_for_payment(state_root: str | Path, payment_receipt: dict[str,Any]) -> dict[str,Any] | None:
    root=Path(state_root); ref=receipt_payment_reference(payment_receipt)
    payment_path=root/"state/commerce/payments"/f"{payment_key(ref)}.json"
    if not payment_path.exists(): return None
    payment_record=_load(payment_path)
    if str(payment_record.get("payment_reference") or "").lower()!=ref:
        raise CommerceInvalid("persistent payment reference mismatch")
    if payment_record.get("payment_receipt")!=payment_receipt:
        raise CommerceInvalid("persistent payment receipt conflict")
    purchase_id=str(payment_record.get("purchase_id") or "")
    if not purchase_id: raise CommerceInvalid("persistent payment record missing purchase id")
    purchase_path=root/"state/commerce/purchases"/f"{purchase_id}.json"
    if not purchase_path.exists(): raise CommerceInvalid("persistent purchase record missing")
    purchase_record=_load(purchase_path)
    grant=purchase_record.get("purchase_grant")
    if not isinstance(grant,dict): raise CommerceInvalid("persistent purchase grant missing")
    if grant.get("purchase_id")!=purchase_id or grant.get("payment_reference")!=ref:
        raise CommerceInvalid("persistent purchase binding mismatch")
    return grant


def settle_proof(*, invoice_record: dict[str,Any], proof: dict[str,Any], state_root: str | Path, rpc_url: str, readiness: dict[str,Any], witness: dict[str,Any], product: dict[str,Any]) -> dict[str,Any]:
    request=invoice_record.get("request"); invoice=invoice_record.get("invoice")
    if not isinstance(request,dict) or not isinstance(invoice,dict): raise CommerceInvalid("invoice record missing request/invoice")
    tx_hash=str(proof.get("tx_hash") or "")
    log_index=proof.get("log_index")
    if log_index is not None: log_index=int(log_index)
    observation=observe_transaction(JsonRpc(rpc_url),invoice["quote"],tx_hash=tx_hash,expected_log_index=log_index)
    result={"schema":"janus.machine_market.paid_search_settlement_result.v1","invoice_id":invoice["invoice_id"],"observation":observation,"settled":False}
    if observation.get("status")!="CONFIRMED": return result
    verify_payment_receipt(invoice["quote"],observation)
    recovered=recover_purchase_for_payment(state_root,observation)
    if recovered is not None:
        grant=recovered
        packet=build_paid_home_packet(request=request,purchase_grant=grant,quote=invoice["quote"],payment_receipt=observation)
        ledger={"payment":"IDEMPOTENT_REPLAY","purchase":"IDEMPOTENT_REPLAY"}
        replayed=True
    else:
        grant,packet=settle_invoice(
            invoice=invoice,request=request,payment_receipt=observation,
            readiness=readiness,witness=witness,product=product,
            consumed_payment_refs=consumed_payment_references(state_root),
        )
        ledger=persist_purchase(state_root,observation,grant)
        replayed=False
    if not verify_paid_home_packet(packet): raise CommerceInvalid("paid HOME packet self-verification failed")
    return {
        **result,
        "settled":True,
        "replayed":replayed,
        "purchase_id":grant["purchase_id"],
        "purchase_grant_hash":grant["grant_hash"],
        "payment_reference":grant["payment_reference"],
        "query_id":packet["query_id"],
        "packet_hash":packet["packet_hash"],
        "ledger":ledger,
        "packet":packet,
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--invoice-record",required=True)
    ap.add_argument("--proof",required=True)
    ap.add_argument("--state-root",required=True)
    ap.add_argument("--rpc-url",required=True)
    ap.add_argument("--readiness",required=True)
    ap.add_argument("--witness",required=True)
    ap.add_argument("--product",required=True)
    ap.add_argument("--result-out",required=True)
    ap.add_argument("--packet-out",required=True)
    args=ap.parse_args()
    out=settle_proof(
        invoice_record=_load(args.invoice_record),proof=_load(args.proof),state_root=args.state_root,rpc_url=args.rpc_url,
        readiness=_load(args.readiness),witness=_load(args.witness),product=_load(args.product),
    )
    Path(args.result_out).write_text(json.dumps({k:v for k,v in out.items() if k!="packet"},ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if out.get("settled"):
        Path(args.packet_out).write_text(json.dumps(out["packet"],ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k!="packet"},ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__": raise SystemExit(main())
