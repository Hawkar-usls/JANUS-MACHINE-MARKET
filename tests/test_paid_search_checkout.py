import json
from datetime import datetime, timezone

import pytest

from runtime.commerce_authority import CommerceBlocked, USDT_ETHEREUM
from runtime.paid_search_checkout import issue_invoice, search_price_usdt_micros, settle_invoice, verify_invoice

TX="0x"+"ab"*32


def pricing(): return json.load(open("PRICING.json",encoding="utf-8"))
def request():
    return {
        "schema":"janus.machine_market.buyer_query_shadow_request.v1",
        "request_id":"github-issue-id:9001",
        "sku":"JANUS.SEARCH",
        "buyer_actor_id":"github:external-buyer",
        "conversation_id":"paid-market-issue-9001",
        "turn_index":0,
        "message_text":"paid checkout test",
        "created_at":"2026-09-04T12:00:00Z",
        "max_turns":1,
        "max_message_utf8_bytes":4000,
        "max_answer_utf8_bytes":6000,
        "conversation_history_turns":0,
        "source_issue_number":9001,
        "source_issue_id":9001001,
        "request_origin":"FOREIGN_PAID_SEARCH",
    }


def invoice(): return issue_invoice(request=request(),pricing=pricing(),issued_at=datetime(2026,9,4,12,0,tzinfo=timezone.utc))
def receipt(inv=None):
    inv=inv or invoice(); q=inv["quote"]
    return {
        "schema":"janus.machine_market.payment_receipt.v1","status":"CONFIRMED","quote_hash":q["quote_hash"],
        "tx_hash":TX,"log_index":7,"payment_reference":f"{TX}:7","chain_id":1,"token_contract":USDT_ETHEREUM,
        "to":q["receiving_address"],"amount_usdt_micros":q["amount_usdt_micros"],"confirmations":12,
        "required_confirmations":12,"block_timestamp":"2026-09-04T12:10:00Z",
    }


def live_readiness(): return {"money_enabled":True,"autonomous_purchase_declared":True}
def live_witness(): return {"foreign_agent_witness":True}
def live_product(): return {"sku":"JANUS.SEARCH","machine_purchase":True}


def test_fast_search_price_is_current_ratecard_005_usdt():
    assert search_price_usdt_micros(pricing())==50_000


def test_invoice_is_deterministic_for_same_immutable_issue_time():
    a=invoice(); b=invoice()
    assert a==b
    verify_invoice(a,request())
    assert a["amount_usdt_micros"]==50_000
    assert a["payment_is_execution_authority"] is False
    assert a["unsolicited_payment_grants_nothing"] is True


def test_canonical_closed_gate_cannot_settle_even_with_valid_payment_shape():
    inv=invoice()
    with pytest.raises(CommerceBlocked,match="money_enabled"):
        settle_invoice(invoice=inv,request=request(),payment_receipt=receipt(inv),readiness={"money_enabled":False,"autonomous_purchase_declared":False},witness={"foreign_agent_witness":False},product={"sku":"JANUS.SEARCH","machine_purchase":False})


def test_settled_invoice_yields_paid_home_packet_not_execution_authority():
    inv=invoice(); grant,packet=settle_invoice(invoice=inv,request=request(),payment_receipt=receipt(inv),readiness=live_readiness(),witness=live_witness(),product=live_product())
    assert grant["status"]=="PURCHASE_SETTLED"
    assert grant["execution_authority_granted"] is False
    assert grant["buyer_query_entitlement"]["buyer_actor_id"]=="github:external-buyer"
    assert packet["mode"]=="PAID_SETTLED"
    assert packet["payment_required"] is True
    assert packet["command_authority_granted"] is False
    assert packet["external_effect_authorized"] is False


def test_used_payment_reference_is_rejected_on_second_purchase():
    inv=invoice(); p=receipt(inv)
    with pytest.raises(ValueError,match="already consumed"):
        settle_invoice(invoice=inv,request=request(),payment_receipt=p,readiness=live_readiness(),witness=live_witness(),product=live_product(),consumed_payment_refs=[p["payment_reference"]])
