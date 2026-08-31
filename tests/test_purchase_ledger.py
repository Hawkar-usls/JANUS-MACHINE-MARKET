from datetime import datetime, timezone

import pytest

from runtime.commerce_authority import USDT_ETHEREUM, admit_purchase, build_quote
from runtime.purchase_ledger import LedgerConflict, consumed_payment_references, persist_purchase

RECEIVER = "0x7149081aea54fbef57effeb52a5a966b81cc03a0"
TX = "0x" + "ab" * 32
REF = f"{TX}:2"
NOW = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)


def request(): return {"schema":"janus.machine_market.request.v1","sku":"JANUS.SEARCH","input":{"query":"ledger"}}
def quote(): return build_quote(request=request(),sku="JANUS.SEARCH",amount_usdt_micros=100_000,receiving_address=RECEIVER,expires_at="2026-08-31T19:00:00+00:00",nonce="ledger-nonce",policy_version="v1")
def receipt():
    q=quote(); return {"schema":"janus.machine_market.payment_receipt.v1","status":"CONFIRMED","quote_hash":q["quote_hash"],"tx_hash":TX,"log_index":2,"payment_reference":REF,"chain_id":1,"token_contract":USDT_ETHEREUM,"to":RECEIVER,"amount_usdt_micros":100_000,"confirmations":12,"required_confirmations":12}
def grant():
    return admit_purchase(readiness={"money_enabled":True,"autonomous_purchase_declared":True},foreign_witness={"foreign_agent_witness":True},product={"sku":"JANUS.SEARCH","machine_purchase":True},request=request(),quote=quote(),payment_receipt=receipt(),now=NOW)


def test_create_then_exact_retry_is_idempotent(tmp_path):
    a=persist_purchase(tmp_path,receipt(),grant()); b=persist_purchase(tmp_path,receipt(),grant())
    assert a["payment"]=="CREATED" and a["purchase"]=="CREATED"
    assert b["payment"]=="IDEMPOTENT_REPLAY" and b["purchase"]=="IDEMPOTENT_REPLAY"
    assert consumed_payment_references(tmp_path)=={REF}


def test_same_payment_reference_cannot_point_to_conflicting_purchase(tmp_path):
    persist_purchase(tmp_path,receipt(),grant()); bad=dict(grant()); bad["purchase_id"]="jp-conflict"
    with pytest.raises(LedgerConflict): persist_purchase(tmp_path,receipt(),bad)


def test_ledger_refuses_purchase_grant_claiming_execution_authority(tmp_path):
    bad=dict(grant()); bad["execution_authority_granted"]=True
    with pytest.raises(ValueError,match="execution authority"): persist_purchase(tmp_path,receipt(),bad)


def test_ledger_requires_settled_purchase(tmp_path):
    bad=dict(grant()); bad["status"]="PURCHASE_ELIGIBLE"
    with pytest.raises(ValueError,match="settled purchase"): persist_purchase(tmp_path,receipt(),bad)


def test_corrupt_persistent_payment_record_fails_closed(tmp_path):
    p=tmp_path/"state/commerce/payments/bad.json"; p.parent.mkdir(parents=True); p.write_text("not-json",encoding="utf-8")
    with pytest.raises(LedgerConflict,match="invalid persistent payment ledger"): consumed_payment_references(tmp_path)
