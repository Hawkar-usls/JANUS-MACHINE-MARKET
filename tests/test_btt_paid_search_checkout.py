from datetime import datetime, timedelta, timezone

import pytest

from runtime.btt_paid_search_checkout import btt_atomic_from_reference, issue_btt_invoice, verify_btt_invoice
from runtime.commerce_authority import CommerceInvalid
from tests.test_paid_search_checkout import pricing

NOW=datetime(2026,9,27,0,0,tzinfo=timezone.utc)


def request(level=1):
    return {
        "schema":"janus.machine_market.buyer_query_shadow_request.v1","request_id":"github-issue-id:99001","sku":"JANUS.SEARCH",
        "buyer_actor_id":"github:external-btt-buyer","conversation_id":"paid-market-issue-99001","turn_index":0,"message_text":"btt paid checkout test",
        "created_at":"2026-09-27T00:00:00Z","max_turns":1,"max_message_utf8_bytes":4000,"max_answer_utf8_bytes":6000,"conversation_history_turns":0,
        "source_issue_number":99001,"source_issue_id":99001001,"request_origin":"FOREIGN_PAID_SEARCH","queue_level":level,"payment_route":"BTT_TRON",
    }


def oracle(price="0.00000050", close=NOW):
    center=float(price)
    bid=f"{center*0.999:.12f}"
    ask=f"{center*1.001:.12f}"
    return {
        "provider":"BINANCE_SPOT_PUBLIC_BOOK_TICKER","endpoint":"https://data-api.binance.vision/api/v3/ticker/bookTicker","symbol":"BTTUSDT",
        "bid_price":bid,"ask_price":ask,"price":f"{center:.12f}","spread_bps":"20","max_spread_bps":500,
        "observed_at":close.isoformat().replace('+00:00','Z'),"fetched_at":NOW.isoformat().replace('+00:00','Z'),
        "close_time_ms":int(close.timestamp()*1000),"close_time":close.isoformat().replace('+00:00','Z'),
        "timestamp_semantics":"HTTPS_FETCH_OBSERVATION_TIME_NOT_LAST_TRADE","max_age_seconds":120,
    }


def test_exact_btt_amount_is_50_percent_discount_and_ceiling_atomic():
    discounted, atomic=btt_atomic_from_reference(reference_usdt_micros=50_000,price_bttusdt="0.00000050")
    assert discounted==25_000
    assert atomic==50_000 * 10**18


def test_btt_invoice_freezes_orderbook_amount_receiver_and_route():
    inv=issue_btt_invoice(request=request(),pricing=pricing(),issued_at=NOW,oracle=oracle())
    verify_btt_invoice(inv,request())
    q=inv["quote"]
    assert inv["reference_usdt_micros"]==50_000
    assert inv["amount_usdt_micros"]==25_000
    assert inv["amount_atomic"]==50_000 * 10**18
    assert q["discount_bps"]==5000
    assert q["payment_route"]=="BTT_TRON"
    assert q["token_contract"]=="TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4"
    assert q["receiving_address"]=="TSqkDJX9uBEnA8mmRc4UN3Bw6hcujcvmd1"
    assert q["rounding"]=="CEILING_TO_BTT_ATOMIC_UNIT"
    assert q["oracle"]["endpoint"]=="https://data-api.binance.vision/api/v3/ticker/bookTicker"
    assert q["oracle"]["timestamp_semantics"]=="HTTPS_FETCH_OBSERVATION_TIME_NOT_LAST_TRADE"


def test_stale_btt_oracle_fails_closed():
    with pytest.raises(CommerceInvalid,match="oracle outside freshness"):
        issue_btt_invoice(request=request(),pricing=pricing(),issued_at=NOW,oracle=oracle(close=NOW-timedelta(minutes=3)))


def test_payment_route_is_cryptographically_bound_by_request_hash():
    inv=issue_btt_invoice(request=request(),pricing=pricing(),issued_at=NOW,oracle=oracle())
    bad=request(); bad["payment_route"]="USDT_ETHEREUM"
    with pytest.raises(CommerceInvalid,match="request binding"):
        verify_btt_invoice(inv,bad)


def test_queue_multiplier_affects_reference_before_btt_discount():
    inv=issue_btt_invoice(request=request(5),pricing=pricing(),issued_at=NOW,oracle=oracle())
    assert inv["reference_usdt_micros"]==250_000
    assert inv["amount_usdt_micros"]==125_000
    assert inv["amount_atomic"]==250_000 * 10**18


def test_wide_orderbook_spread_fails_closed():
    o=oracle(); o["bid_price"]="0.00000040"; o["ask_price"]="0.00000060"; o["price"]="0.00000050"
    with pytest.raises(CommerceInvalid,match="spread exceeds"):
        issue_btt_invoice(request=request(),pricing=pricing(),issued_at=NOW,oracle=o)
