#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.btt_paid_search_checkout import verify_btt_invoice
from runtime.commerce_authority import CommerceBlocked, CommerceInvalid, admit_purchase, verify_payment_receipt
from runtime.paid_search_checkout import checkout_gate
from runtime.paid_search_packet import build_paid_home_packet, verify_paid_home_packet
from runtime.paid_search_queue import build_queue_entry, enqueue, snapshot
from runtime.paid_search_settlement import recover_purchase_for_payment
from runtime.purchase_ledger import consumed_payment_references, persist_purchase
from runtime.tron_btt_observer import TronHttp, TronRpcError, observe_btt_transfer


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise CommerceInvalid(f"expected object: {path}")
    return value


def settle_btt_proof(
    *,
    invoice_record: dict[str, Any],
    proof: dict[str, Any],
    state_root: str | Path,
    readiness: dict[str, Any],
    witness: dict[str, Any],
    product: dict[str, Any],
    queue_policy: dict[str, Any] | None = None,
    tron_client: TronHttp | None = None,
) -> dict[str, Any]:
    request = invoice_record.get("request"); invoice = invoice_record.get("invoice")
    if not isinstance(request, dict) or not isinstance(invoice, dict): raise CommerceInvalid("invoice record missing request/invoice")
    if str(request.get("payment_route") or "") != "BTT_TRON": raise CommerceInvalid("BTT settlement requires BTT_TRON request route")
    checkout_gate(readiness=readiness, witness=witness, product=product)
    verify_btt_invoice(invoice, request)
    txid = str(proof.get("txid") or proof.get("tx_hash") or "")
    event_index = proof.get("event_index")
    if event_index is not None: event_index = int(event_index)
    observation = observe_btt_transfer(tron_client or TronHttp(), invoice["quote"], txid=txid, expected_event_index=event_index)
    result: dict[str, Any] = {
        "schema":"janus.machine_market.btt_paid_search_settlement_result.v1",
        "invoice_id":invoice["invoice_id"],"observation":observation,"settled":False,
    }
    if observation.get("status") != "CONFIRMED": return result
    verify_payment_receipt(invoice["quote"], observation)
    recovered = recover_purchase_for_payment(state_root, observation)
    if recovered is not None:
        grant = recovered
        packet = build_paid_home_packet(request=request,purchase_grant=grant,quote=invoice["quote"],payment_receipt=observation)
        ledger = {"payment":"IDEMPOTENT_REPLAY","purchase":"IDEMPOTENT_REPLAY"}; replayed=True
    else:
        grant = admit_purchase(
            readiness=readiness,foreign_witness=witness,product=product,request=request,quote=invoice["quote"],payment_receipt=observation,
            consumed_payment_refs=consumed_payment_references(state_root),buyer_actor_id=str(request.get("buyer_actor_id") or ""),
        )
        packet = build_paid_home_packet(request=request,purchase_grant=grant,quote=invoice["quote"],payment_receipt=observation)
        ledger = persist_purchase(state_root, observation, grant); replayed=False
    if not verify_paid_home_packet(packet): raise CommerceInvalid("BTT paid HOME packet self-verification failed")
    queue_result=None; queue_snapshot=None
    if queue_policy is not None:
        entry=build_queue_entry(request=request,purchase_grant=grant,packet=packet,payment_receipt=observation,policy=queue_policy)
        queue_result=enqueue(state_root,entry,queue_policy)
        queue_snapshot=snapshot(state_root,queue_policy,now=datetime.now(timezone.utc),focus_purchase_id=grant["purchase_id"])
    return {
        **result,"settled":True,"replayed":replayed,"purchase_id":grant["purchase_id"],"purchase_grant_hash":grant["grant_hash"],
        "payment_reference":grant["payment_reference"],"canonical_payment_receipt":observation,"query_id":packet["query_id"],"packet_hash":packet["packet_hash"],
        "queue_level":int(request.get("queue_level",1)),"execution_started":False,"ledger":ledger,"queue":queue_result,"queue_snapshot":queue_snapshot,"packet":packet,
    }


def _public_result(out: dict[str, Any]) -> dict[str, Any]: return {k:v for k,v in out.items() if k != "packet"}


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--invoice-record",required=True); ap.add_argument("--proof",required=True); ap.add_argument("--state-root",required=True)
    ap.add_argument("--readiness",required=True); ap.add_argument("--witness",required=True); ap.add_argument("--product",required=True); ap.add_argument("--queue-policy")
    ap.add_argument("--tron-base-url",default="https://api.trongrid.io"); ap.add_argument("--result-out",required=True); ap.add_argument("--packet-out",required=True)
    args=ap.parse_args(); record=_load(args.invoice_record)
    try:
        out=settle_btt_proof(
            invoice_record=record,proof=_load(args.proof),state_root=args.state_root,readiness=_load(args.readiness),witness=_load(args.witness),product=_load(args.product),
            queue_policy=_load(args.queue_policy) if args.queue_policy else None,tron_client=TronHttp(args.tron_base_url),
        )
    except (CommerceInvalid,CommerceBlocked,TronRpcError,ValueError,RuntimeError) as exc:
        inv=record.get("invoice") or {}; reason=str(exc).replace("\n"," ")[:200]
        out={"schema":"janus.machine_market.btt_paid_search_settlement_result.v1","invoice_id":str(inv.get("invoice_id") or ""),"observation":{"status":"REJECTED","reason":reason},"settled":False,"reason":reason}
    public=_public_result(out)
    Path(args.result_out).write_text(json.dumps(public,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if out.get("settled"):
        Path(args.packet_out).write_text(json.dumps(out["packet"],ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(public,ensure_ascii=False,sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
