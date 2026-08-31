from datetime import datetime, timezone

import pytest

from runtime.commerce_authority import (
    CommerceBlocked,
    CommerceInvalid,
    USDT_ETHEREUM,
    admit_purchase,
    build_quote,
)

RECEIVER = "0x7149081aea54fbef57effeb52a5a966b81cc03a0"
TX = "0x" + "ab" * 32
LOG_INDEX = 7
PAYMENT_REF = f"{TX}:{LOG_INDEX}"
NOW = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)


def request():
    return {"schema": "janus.machine_market.request.v1", "sku": "JANUS.SEARCH", "input": {"query": "test"}}


def quote():
    return build_quote(
        request=request(), sku="JANUS.SEARCH", amount_usdt_micros=50_000,
        receiving_address=RECEIVER, expires_at="2026-08-31T19:00:00+00:00",
        nonce="nonce-1", policy_version="commerce-v1",
    )


def receipt(amount=50_000, confirmations=12, required_confirmations=12, log_index=LOG_INDEX):
    q = quote()
    return {
        "schema": "janus.machine_market.payment_receipt.v1",
        "status": "CONFIRMED",
        "quote_hash": q["quote_hash"],
        "tx_hash": TX,
        "log_index": log_index,
        "payment_reference": f"{TX}:{log_index}",
        "chain_id": 1,
        "token_contract": USDT_ETHEREUM,
        "to": RECEIVER,
        "amount_usdt_micros": amount,
        "confirmations": confirmations,
        "required_confirmations": required_confirmations,
    }


def live_readiness(): return {"money_enabled": True, "autonomous_purchase_declared": True}
def witness(value=True): return {"foreign_agent_witness": value}
def product(machine_purchase=True): return {"sku": "JANUS.SEARCH", "machine_purchase": machine_purchase}


def test_canonical_current_state_blocks_money():
    with pytest.raises(CommerceBlocked, match="money_enabled"):
        admit_purchase(readiness={"money_enabled": False, "autonomous_purchase_declared": False}, foreign_witness=witness(False), product=product(False), request=request(), quote=quote(), payment_receipt=receipt(), now=NOW)


def test_foreign_witness_is_mandatory_even_when_money_switch_is_on():
    with pytest.raises(CommerceBlocked, match="foreign agent witness"):
        admit_purchase(readiness=live_readiness(), foreign_witness=witness(False), product=product(True), request=request(), quote=quote(), payment_receipt=receipt(), now=NOW)


def test_exact_payment_and_open_product_produce_deterministic_purchase_grant():
    kwargs = dict(readiness=live_readiness(), foreign_witness=witness(True), product=product(True), request=request(), quote=quote(), payment_receipt=receipt(), now=NOW)
    a = admit_purchase(**kwargs); b = admit_purchase(**kwargs)
    assert a == b
    assert a["purchase_id"].startswith("jp-")
    assert a["payment_reference"] == PAYMENT_REF
    assert a["execution_authority"] is False
    assert a["next_gate"] == "JANUS_POLICY_SCOPE_TO_EXECUTION_GRANT"


def test_wrong_amount_is_rejected():
    with pytest.raises(CommerceInvalid, match="amount mismatch"):
        admit_purchase(readiness=live_readiness(), foreign_witness=witness(True), product=product(True), request=request(), quote=quote(), payment_receipt=receipt(amount=49_999), now=NOW)


def test_underconfirmed_payment_is_rejected():
    with pytest.raises(CommerceInvalid, match="confirmation threshold"):
        admit_purchase(readiness=live_readiness(), foreign_witness=witness(True), product=product(True), request=request(), quote=quote(), payment_receipt=receipt(confirmations=11), now=NOW)


def test_receipt_cannot_weaken_confirmation_policy():
    with pytest.raises(CommerceInvalid, match="weakens confirmation policy"):
        admit_purchase(readiness=live_readiness(), foreign_witness=witness(True), product=product(True), request=request(), quote=quote(), payment_receipt=receipt(confirmations=6, required_confirmations=6), now=NOW)


def test_consumed_transfer_log_cannot_be_reused():
    with pytest.raises(CommerceInvalid, match="already consumed"):
        admit_purchase(readiness=live_readiness(), foreign_witness=witness(True), product=product(True), request=request(), quote=quote(), payment_receipt=receipt(), consumed_payment_refs=[PAYMENT_REF], now=NOW)


def test_tx_can_contain_another_distinct_transfer_log_identity():
    alt = receipt(log_index=8)
    grant = admit_purchase(readiness=live_readiness(), foreign_witness=witness(True), product=product(True), request=request(), quote=quote(), payment_receipt=alt, consumed_payment_refs=[PAYMENT_REF], now=NOW)
    assert grant["payment_reference"] == f"{TX}:8"


def test_payment_reference_must_match_tx_and_log_index():
    r = receipt(); r["payment_reference"] = f"{TX}:999"
    with pytest.raises(CommerceInvalid, match="payment reference mismatch"):
        admit_purchase(readiness=live_readiness(), foreign_witness=witness(True), product=product(True), request=request(), quote=quote(), payment_receipt=r, now=NOW)
