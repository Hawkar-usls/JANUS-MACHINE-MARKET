#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from runtime.commerce_authority import (
    CommerceBlocked,
    CommerceInvalid,
    admit_purchase,
    build_quote,
    digest,
    parse_time,
    request_hash,
    verify_quote,
)
from runtime.paid_search_packet import build_paid_home_packet

SKU="JANUS.SEARCH"
MODE="FAST"
POLICY_VERSION="commerce-paid-search-v1"
INVOICE_SCHEMA="janus.machine_market.paid_search_invoice.v1"
DEFAULT_RECEIVER="0x7149081aea54fbef57effeb52a5a966b81cc03a0"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CommerceInvalid(message)


def checkout_gate(*, readiness: dict[str,Any], witness: dict[str,Any], product: dict[str,Any]) -> None:
    if readiness.get("money_enabled") is not True:
        raise CommerceBlocked("money_enabled is false")
    if readiness.get("autonomous_purchase_declared") is not True:
        raise CommerceBlocked("autonomous purchase is not declared")
    if witness.get("foreign_agent_witness") is not True:
        raise CommerceBlocked("foreign agent witness is not established")
    if product.get("sku") != SKU or product.get("machine_purchase") is not True:
        raise CommerceBlocked("JANUS.SEARCH machine purchase is not live")


def search_price_usdt_micros(pricing: dict[str,Any], *, mode: str=MODE) -> int:
    _require(pricing.get("currency")=="USDT", "pricing asset invalid")
    _require(int(pricing.get("chain_id",-1))==1, "pricing chain invalid")
    product=(pricing.get("products") or {}).get(SKU)
    _require(isinstance(product,dict), "JANUS.SEARCH pricing missing")
    modes=product.get("modes") or {}
    _require(mode in modes, "paid search mode not priced")
    base=int(product.get("base_unit_usdt_micros",0)); bps=int(modes[mode].get("multiplier_bps",0))
    _require(base>0 and bps>0, "paid search price invalid")
    amount=(base*bps)//10_000
    _require(amount>0, "paid search amount invalid")
    return amount


def issue_invoice(*, request: dict[str,Any], pricing: dict[str,Any], issued_at: datetime, receiving_address: str=DEFAULT_RECEIVER, mode: str=MODE) -> dict[str,Any]:
    if issued_at.tzinfo is None:
        raise CommerceInvalid("issued_at must be timezone-aware")
    issued_at=issued_at.astimezone(timezone.utc)
    ttl=int(pricing.get("quote_ttl_seconds",0))
    _require(60 <= ttl <= 3600, "quote ttl outside production bounds")
    amount=search_price_usdt_micros(pricing,mode=mode)
    req_hash=request_hash(request)
    issued_text=issued_at.isoformat().replace("+00:00","Z")
    nonce="paid-search-"+digest({"request_hash":req_hash,"issued_at":issued_text,"mode":mode,"policy_version":POLICY_VERSION})[:32]
    expires=(issued_at+timedelta(seconds=ttl)).isoformat()
    quote=build_quote(request=request,sku=SKU,amount_usdt_micros=amount,receiving_address=receiving_address,expires_at=expires,nonce=nonce,policy_version=POLICY_VERSION)
    invoice_id="inv-search-"+digest({"request_hash":req_hash,"quote_hash":quote["quote_hash"]})[:40]
    invoice={
        "schema":INVOICE_SCHEMA,
        "invoice_id":invoice_id,
        "sku":SKU,
        "mode":mode,
        "buyer_actor_id":request.get("buyer_actor_id"),
        "request_id":request.get("request_id"),
        "request_hash":req_hash,
        "issued_at":issued_text,
        "expires_at":quote["expires_at"],
        "quote":quote,
        "quote_hash":quote["quote_hash"],
        "amount_usdt_micros":amount,
        "asset":"USDT",
        "network":"ethereum-mainnet",
        "chain_id":1,
        "receiving_address":quote["receiving_address"],
        "payment_required":True,
        "payment_is_execution_authority":False,
        "unsolicited_payment_grants_nothing":True,
        "status":"AWAITING_PAYMENT",
    }
    invoice["invoice_hash"]=digest(invoice)
    return invoice


def verify_invoice(invoice: dict[str,Any], request: dict[str,Any]) -> None:
    body=dict(invoice); claimed=str(body.pop("invoice_hash", ""))
    _require(len(claimed)==64 and digest(body)==claimed, "invoice hash invalid")
    _require(invoice.get("schema")==INVOICE_SCHEMA and invoice.get("sku")==SKU, "invoice schema or sku invalid")
    _require(invoice.get("request_hash")==request_hash(request), "invoice request binding mismatch")
    _require(invoice.get("quote_hash")==invoice.get("quote",{}).get("quote_hash"), "invoice quote binding mismatch")
    _require(invoice.get("buyer_actor_id")==request.get("buyer_actor_id"), "invoice buyer binding mismatch")
    _require(invoice.get("payment_is_execution_authority") is False, "invoice authority invalid")
    verify_quote(invoice["quote"],request,now=parse_time(invoice["issued_at"]),require_unexpired=True)


def settle_invoice(*, invoice: dict[str,Any], request: dict[str,Any], payment_receipt: dict[str,Any], readiness: dict[str,Any], witness: dict[str,Any], product: dict[str,Any], consumed_payment_refs: Iterable[str]=()) -> tuple[dict[str,Any],dict[str,Any]]:
    checkout_gate(readiness=readiness,witness=witness,product=product)
    verify_invoice(invoice,request)
    grant=admit_purchase(
        readiness=readiness,
        foreign_witness=witness,
        product=product,
        request=request,
        quote=invoice["quote"],
        payment_receipt=payment_receipt,
        consumed_payment_refs=consumed_payment_refs,
        buyer_actor_id=str(request.get("buyer_actor_id") or ""),
    )
    packet=build_paid_home_packet(request=request,purchase_grant=grant,quote=invoice["quote"],payment_receipt=payment_receipt)
    return grant,packet


__all__=["DEFAULT_RECEIVER","INVOICE_SCHEMA","MODE","POLICY_VERSION","checkout_gate","issue_invoice","search_price_usdt_micros","settle_invoice","verify_invoice"]
