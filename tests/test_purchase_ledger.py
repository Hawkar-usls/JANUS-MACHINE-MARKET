from datetime import datetime, timezone

import pytest

from runtime.commerce_authority import USDT_ETHEREUM, admit_purchase, build_quote
from runtime.purchase_ledger import LedgerConflict, consumed_payment_references, persist_execution_result, persist_purchase

RECEIVER="0x7149081aea54fbef57effeb52a5a966b81cc03a0"
TX="0x"+"ab"*32
REF=f"{TX}:2"
NOW=datetime(2026,8,31,18,0,tzinfo=timezone.utc)


def request(): return {"schema":"janus.machine_market.request.v1","sku":"JANUS.SEARCH","input":{"query":"ledger"}}
def quote(): return build_quote(request=request(),sku="JANUS.SEARCH",amount_usdt_micros=100_000,receiving_address=RECEIVER,expires_at="2026-08-31T19:00:00+00:00",nonce="ledger-nonce",policy_version="v1")
def receipt():
    q=quote(); return {"schema":"janus.machine_market.payment_receipt.v1","status":"CONFIRMED","quote_hash":q["quote_hash"],"tx_hash":TX,"log_index":2,"payment_reference":REF,"chain_id":1,"token_contract":USDT_ETHEREUM,"to":RECEIVER,"amount_usdt_micros":100_000,"confirmations":12,"required_confirmations":12}
def grant(): return admit_purchase(readiness={"money_enabled":True,"autonomous_purchase_declared":True},foreign_witness={"foreign_agent_witness":True},product={"sku":"JANUS.SEARCH","machine_purchase":True},request=request(),quote=quote(),payment_receipt=receipt(),now=NOW)
def result_receipt(execution_id="exe-1",result_hash="1"*64):
    p=grant()
    return {"schema":"janus.machine_market.result_receipt.v1","purchase_id":p["purchase_id"],"sku":"JANUS.SEARCH","payment_reference":REF,"purchase_grant_hash":p["grant_hash"],"execution_grant_hash":"2"*64,"request_sha256":p["request_hash"],"result_sha256":result_hash,"status":"DELIVERED","organ":"TEST","runtime":{"engine":"TEST"},"resource_usage":{},"price":{"asset":"USDT"},"settlement_reference":REF,"result_reference":None,"inline_result":{},"execution_receipt":{"schema":"janus.machine_market.execution_receipt.v1","execution_id":execution_id,"grant_id":"eg-test","purchase_id":p["purchase_id"],"authority_class":"BOUNDED_COMMERCE_SEARCH","request_hash":p["request_hash"],"result_sha256":result_hash,"network_access_used":False,"external_effects":False}}


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


def test_execution_result_exact_retry_is_idempotent(tmp_path):
    r=result_receipt(); a=persist_execution_result(tmp_path,r); b=persist_execution_result(tmp_path,r)
    assert a["purchase_execution_index"]=="CREATED" and a["execution"]=="CREATED"
    assert b["purchase_execution_index"]=="IDEMPOTENT_REPLAY" and b["execution"]=="IDEMPOTENT_REPLAY"


def test_second_execution_identity_for_same_purchase_is_rejected(tmp_path):
    persist_execution_result(tmp_path,result_receipt("exe-1","1"*64))
    with pytest.raises(LedgerConflict): persist_execution_result(tmp_path,result_receipt("exe-2","2"*64))


def test_execution_result_with_external_effects_is_rejected(tmp_path):
    r=result_receipt(); r["execution_receipt"]["external_effects"]=True
    with pytest.raises(ValueError,match="external-effect"): persist_execution_result(tmp_path,r)


def test_corrupt_persistent_payment_record_fails_closed(tmp_path):
    p=tmp_path/"state/commerce/payments/bad.json"; p.parent.mkdir(parents=True); p.write_text("not-json",encoding="utf-8")
    with pytest.raises(LedgerConflict,match="invalid persistent payment ledger"): consumed_payment_references(tmp_path)
