#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from runtime.commerce_authority import (
    BTT_DECIMALS,
    BTT_RECEIVER,
    BTT_TRON,
    TRON_NETWORK,
    CommerceInvalid,
    digest,
    parse_time,
    request_hash,
    verify_quote,
)
from runtime.paid_search_checkout import MODE, SKU, search_price_usdt_micros

INVOICE_SCHEMA = "janus.machine_market.btt_paid_search_invoice.v1"
POLICY_VERSION = "commerce-paid-search-btt-tron-v1"
ORACLE_PROVIDER = "BINANCE_SPOT_PUBLIC_BOOK_TICKER"
# Binance renamed the post-redenomination BitTorrent token ticker to BTTC.
# The payment asset remains the new BitTorrent Token on TRON (contract TAFj...).
ORACLE_SYMBOL = "BTTCUSDT"
ORACLE_ENDPOINT = "https://data-api.binance.vision/api/v3/ticker/bookTicker"
MAX_ORACLE_AGE_SECONDS = 120
MAX_SPREAD_BPS = 500
DISCOUNT_BPS = 5000


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CommerceInvalid(message)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise CommerceInvalid("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_bttusdt_oracle(*, now: datetime | None = None, timeout: int = 10) -> dict[str, Any]:
    """Freeze the current Binance BTTC/USDT best bid/ask and midpoint.

    Binance uses BTTC as the exchange ticker for the post-redenomination
    BitTorrent token. The timestamp is the HTTPS observation time, not the
    last-trade time, while the spread gate prevents a zero/empty book from
    becoming a payable quote.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    url = ORACLE_ENDPOINT + "?" + urlencode({"symbol": ORACLE_SYMBOL})
    req = Request(url, headers={"User-Agent":"JANUS-MACHINE-MARKET/1.0","Accept":"application/json"})
    with urlopen(req, timeout=timeout) as response:
        if int(getattr(response,"status",200)) != 200:
            raise CommerceInvalid("BTT oracle HTTP failure")
        payload = json.loads(response.read().decode("utf-8"))
    try:
        bid = Decimal(str(payload["bidPrice"]))
        ask = Decimal(str(payload["askPrice"]))
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise CommerceInvalid("BTT order-book oracle response invalid") from exc
    _require(bid > 0 and ask > 0, "BTT order-book bid/ask must be positive")
    _require(ask >= bid, "BTT order-book is crossed")
    midpoint = (bid + ask) / Decimal(2)
    spread_bps = ((ask - bid) / midpoint * Decimal(10_000)) if midpoint else Decimal("Infinity")
    _require(spread_bps <= Decimal(MAX_SPREAD_BPS), "BTT order-book spread exceeds invoice ceiling")
    observed = _iso(now)
    observed_ms = int(now.timestamp() * 1000)
    return {
        "provider": ORACLE_PROVIDER,
        "endpoint": ORACLE_ENDPOINT,
        "symbol": ORACLE_SYMBOL,
        "exchange_ticker": "BTTC",
        "payment_asset": "BTT",
        "bid_price": format(bid, "f"),
        "ask_price": format(ask, "f"),
        "price": format(midpoint, "f"),
        "spread_bps": format(spread_bps, "f"),
        "max_spread_bps": MAX_SPREAD_BPS,
        "observed_at": observed,
        "fetched_at": observed,
        "close_time_ms": observed_ms,
        "close_time": observed,
        "timestamp_semantics": "HTTPS_FETCH_OBSERVATION_TIME_NOT_LAST_TRADE",
        "max_age_seconds": MAX_ORACLE_AGE_SECONDS,
    }


def discounted_reference_micros(reference_usdt_micros: int) -> int:
    ref = int(reference_usdt_micros)
    _require(ref > 0, "canonical USDT reference must be positive")
    return (ref * (10_000 - DISCOUNT_BPS) + 9_999) // 10_000


def btt_atomic_from_reference(*, reference_usdt_micros: int, price_bttusdt: str) -> tuple[int, int]:
    discounted = discounted_reference_micros(reference_usdt_micros)
    try:
        price = Decimal(str(price_bttusdt))
    except InvalidOperation as exc:
        raise CommerceInvalid("invalid BTTUSDT price") from exc
    _require(price > 0, "BTTUSDT price must be positive")
    discounted_usdt = Decimal(discounted) / Decimal(1_000_000)
    atomic = (discounted_usdt / price * (Decimal(10) ** BTT_DECIMALS)).to_integral_value(rounding=ROUND_CEILING)
    amount = int(atomic)
    _require(amount > 0, "exact BTT amount must be positive")
    return discounted, amount


def _queue_spec(pricing: dict[str, Any], level: int) -> dict[str, Any]:
    levels = ((pricing.get("products") or {}).get(SKU) or {}).get("queue_levels") or {}
    spec = levels.get(str(int(level)))
    _require(isinstance(spec, dict), "BTT invoice queue level is not priced")
    return spec


def issue_btt_invoice(*, request: dict[str, Any], pricing: dict[str, Any], issued_at: datetime, oracle: dict[str, Any] | None = None, mode: str = MODE) -> dict[str, Any]:
    issued_at = issued_at.astimezone(timezone.utc)
    ttl = int(pricing.get("quote_ttl_seconds", 0))
    _require(60 <= ttl <= 3600, "quote ttl outside production bounds")
    _require(str(request.get("payment_route") or "") == "BTT_TRON", "BTT invoice requires payment_route=BTT_TRON")
    queue_level = int(request.get("queue_level", 1))
    spec = _queue_spec(pricing, queue_level)
    reference = search_price_usdt_micros(pricing, mode=mode, queue_level=queue_level)
    oracle = dict(oracle or fetch_bttusdt_oracle(now=issued_at))
    _require(oracle.get("provider") == ORACLE_PROVIDER and oracle.get("symbol") == ORACLE_SYMBOL, "BTT oracle identity invalid")
    observed = parse_time(str(oracle.get("observed_at") or oracle.get("close_time") or ""))
    age = (issued_at - observed).total_seconds()
    _require(-60 <= age <= MAX_ORACLE_AGE_SECONDS, "BTT invoice oracle outside freshness window")
    if oracle.get("bid_price") is not None and oracle.get("ask_price") is not None:
        bid=Decimal(str(oracle["bid_price"])); ask=Decimal(str(oracle["ask_price"])); midpoint=(bid+ask)/Decimal(2)
        _require(bid>0 and ask>=bid and str(midpoint)==str(Decimal(str(oracle["price"]))), "BTT oracle midpoint binding invalid")
        spread=((ask-bid)/midpoint*Decimal(10_000)) if midpoint else Decimal("Infinity")
        _require(spread <= Decimal(int(oracle.get("max_spread_bps",MAX_SPREAD_BPS))), "BTT order-book spread exceeds invoice ceiling")
    discounted, amount_atomic = btt_atomic_from_reference(reference_usdt_micros=reference, price_bttusdt=str(oracle["price"]))
    issued_text = _iso(issued_at)
    expires = _iso(issued_at + timedelta(seconds=ttl))
    req_hash = request_hash(request)
    nonce = "paid-search-btt-" + digest({"request_hash":req_hash,"issued_at":issued_text,"queue_level":queue_level,"policy_version":POLICY_VERSION,"oracle":oracle,"amount_atomic":amount_atomic})[:32]
    quote_body = {
        "schema":"janus.machine_market.quote.v1","sku":SKU,"request_hash":req_hash,"payment_route":"BTT_TRON","amount_usdt_micros":discounted,
        "reference_usdt_micros":reference,"discount_bps":DISCOUNT_BPS,"asset":"BTT","network":TRON_NETWORK,"token_standard":"TRC-20",
        "token_contract":BTT_TRON,"decimals":BTT_DECIMALS,"amount_atomic":amount_atomic,"receiving_address":BTT_RECEIVER,"oracle":oracle,
        "rounding":"CEILING_TO_BTT_ATOMIC_UNIT","expires_at":expires,"nonce":nonce,"policy_version":POLICY_VERSION,
    }
    quote = {**quote_body, "quote_hash": digest(quote_body)}
    verify_quote(quote, request, now=issued_at, require_unexpired=True)
    invoice_id = "inv-search-btt-" + digest({"request_hash":req_hash,"quote_hash":quote["quote_hash"]})[:40]
    invoice = {
        "schema":INVOICE_SCHEMA,"invoice_id":invoice_id,"sku":SKU,"mode":mode,"payment_route":"BTT_TRON","queue_level":queue_level,
        "queue_code":spec.get("code"),"queue_multiplier_bps":int(spec.get("multiplier_bps",0)),"queue_level_is_frozen":True,"active_request_preemption_allowed":False,
        "buyer_actor_id":request.get("buyer_actor_id"),"request_id":request.get("request_id"),"request_hash":req_hash,"issued_at":issued_text,"expires_at":expires,
        "quote":quote,"quote_hash":quote["quote_hash"],"reference_usdt_micros":reference,"amount_usdt_micros":discounted,"discount_bps":DISCOUNT_BPS,
        "asset":"BTT","network":TRON_NETWORK,"token_contract":BTT_TRON,"amount_atomic":amount_atomic,"receiving_address":BTT_RECEIVER,
        "payment_required":True,"payment_is_execution_authority":False,"payment_settled_is_execution_started":False,"unsolicited_payment_grants_nothing":True,"status":"AWAITING_PAYMENT",
    }
    invoice["invoice_hash"] = digest(invoice)
    return invoice


def verify_btt_invoice(invoice: dict[str, Any], request: dict[str, Any]) -> None:
    body = dict(invoice); claimed = str(body.pop("invoice_hash", ""))
    _require(len(claimed) == 64 and digest(body) == claimed, "BTT invoice hash invalid")
    _require(invoice.get("schema") == INVOICE_SCHEMA and invoice.get("payment_route") == "BTT_TRON", "BTT invoice schema/route invalid")
    _require(invoice.get("request_hash") == request_hash(request), "BTT invoice request binding mismatch")
    _require(invoice.get("quote_hash") == (invoice.get("quote") or {}).get("quote_hash"), "BTT invoice quote binding mismatch")
    _require(invoice.get("buyer_actor_id") == request.get("buyer_actor_id"), "BTT invoice buyer binding mismatch")
    _require(invoice.get("payment_is_execution_authority") is False, "BTT invoice authority invalid")
    verify_quote(invoice["quote"], request, now=parse_time(invoice["issued_at"]), require_unexpired=True)


__all__ = ["DISCOUNT_BPS","INVOICE_SCHEMA","MAX_ORACLE_AGE_SECONDS","MAX_SPREAD_BPS","ORACLE_ENDPOINT","ORACLE_PROVIDER","ORACLE_SYMBOL","POLICY_VERSION","btt_atomic_from_reference","discounted_reference_micros","fetch_bttusdt_oracle","issue_btt_invoice","verify_btt_invoice"]
