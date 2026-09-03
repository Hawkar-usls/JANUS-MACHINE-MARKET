from datetime import datetime, timezone

from runtime.commerce_authority import USDT_ETHEREUM, admit_purchase, build_quote
from runtime.paid_search_packet import build_paid_home_packet, verify_paid_home_packet

RECEIVER="0x7149081aea54fbef57effeb52a5a966b81cc03a0"
TX="0x"+"ab"*32


def request():
    return {
        "schema":"janus.machine_market.buyer_query_shadow_request.v1",
        "request_id":"github-issue-id:9001",
        "sku":"JANUS.SEARCH",
        "buyer_actor_id":"github:external-buyer",
        "conversation_id":"paid-market-issue-9001",
        "turn_index":0,
        "message_text":"paid search test",
        "created_at":"2026-09-04T12:00:00Z",
        "max_turns":1,
        "max_message_utf8_bytes":4000,
        "max_answer_utf8_bytes":6000,
        "conversation_history_turns":0,
        "source_issue_number":9001,
        "source_issue_id":9001001,
        "request_origin":"FOREIGN_PAID_SEARCH",
    }


def quote():
    return build_quote(request=request(),sku="JANUS.SEARCH",amount_usdt_micros=50_000,receiving_address=RECEIVER,expires_at="2026-09-04T12:15:00+00:00",nonce="q-9001",policy_version="commerce-paid-search-v1")


def payment(q=None):
    q=q or quote(); return {
        "schema":"janus.machine_market.payment_receipt.v1",
        "status":"CONFIRMED",
        "quote_hash":q["quote_hash"],
        "tx_hash":TX,
        "log_index":7,
        "payment_reference":f"{TX}:7",
        "chain_id":1,
        "token_contract":USDT_ETHEREUM,
        "to":RECEIVER,
        "amount_usdt_micros":50_000,
        "confirmations":12,
        "required_confirmations":12,
        "block_timestamp":"2026-09-04T12:10:00Z",
    }


def settled():
    q=quote(); p=payment(q)
    g=admit_purchase(
        readiness={"money_enabled":True,"autonomous_purchase_declared":True},
        foreign_witness={"foreign_agent_witness":True},
        product={"sku":"JANUS.SEARCH","machine_purchase":True},
        request=request(),quote=q,payment_receipt=p,
        now=datetime(2026,9,4,13,0,tzinfo=timezone.utc),
        buyer_actor_id="github:external-buyer",
    )
    return q,p,g


def test_paid_packet_roundtrip_contract_is_self_verifying():
    q,p,g=settled(); packet=build_paid_home_packet(request=request(),purchase_grant=g,quote=q,payment_receipt=p)
    assert verify_paid_home_packet(packet)
    assert packet["mode"]=="PAID_SETTLED"
    assert packet["money_enabled"] is True
    assert packet["payment_required"] is True
    assert packet["production_purchase"] is True
    assert packet["execution_authority_granted"] is False
    assert packet["command_authority_granted"] is False
    assert packet["external_effect_authorized"] is False
    assert packet["commerce"]["payment_reference"]==f"{TX}:7"


def test_paid_packet_exact_rebuild_is_deterministic():
    q,p,g=settled()
    a=build_paid_home_packet(request=request(),purchase_grant=g,quote=q,payment_receipt=p)
    b=build_paid_home_packet(request=request(),purchase_grant=g,quote=q,payment_receipt=p)
    assert a==b


def test_paid_packet_tamper_fails_verifier():
    q,p,g=settled(); packet=build_paid_home_packet(request=request(),purchase_grant=g,quote=q,payment_receipt=p)
    packet["buyer_query"]["message_text"]="tampered"
    assert not verify_paid_home_packet(packet)


def test_payment_cannot_upgrade_command_authority():
    q,p,g=settled(); packet=build_paid_home_packet(request=request(),purchase_grant=g,quote=q,payment_receipt=p)
    packet["command_authority_granted"]=True
    from runtime.commerce_authority import digest
    body=dict(packet); body.pop("packet_hash",None); packet["packet_hash"]=digest(body)
    assert not verify_paid_home_packet(packet)
