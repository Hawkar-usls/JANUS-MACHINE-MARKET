import json
from pathlib import Path

import pytest

from runtime.purchase_ledger import LedgerConflict, persist_paid_home_response, purchase_key
from runtime.r1b_home_response_reconcile import HomeResponseError, digest, reconcile_response, verify_home_response
from tests.test_r1b_home_response_reconcile import home_response

TX="0x"+"ab"*32
PAYMENT_REF=f"{TX}:7"


def paid_response():
    value=home_response()
    value["mode"]="PAID_SETTLED"
    value["money_enabled"]=True
    value["payment_required"]=True
    value["production_purchase"]=True
    value["payment_reference"]=PAYMENT_REF
    value["buyer_query_receipt"]["payment_reference"]=PAYMENT_REF
    value["buyer_query_receipt"]["billable_execution_delta"]=1
    value.pop("home_response_hash",None)
    value["home_response_hash"]=digest(value)
    return value


def seed_purchase(state: Path, response: dict):
    path=state/"state/commerce/purchases"/f"{response['purchase_id']}.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    grant={
        "schema":"janus.machine_market.purchase_grant.v1",
        "purchase_id":response["purchase_id"],
        "payment_reference":PAYMENT_REF,
        "grant_hash":response["purchase_grant_hash"],
        "status":"PURCHASE_SETTLED",
        "execution_authority_granted":False,
    }
    path.write_text(json.dumps({"schema":"janus.machine_market.purchase_ledger_record.v1","purchase_id":response["purchase_id"],"payment_reference":PAYMENT_REF,"purchase_grant":grant},sort_keys=True,indent=2)+"\n")


def alternate_execution(response: dict) -> dict:
    other=json.loads(json.dumps(response))
    other["terminal_response"]["response_id"]="tr-other"
    other["terminal_response"].pop("response_hash",None)
    other["terminal_response"]["response_hash"]=digest(other["terminal_response"])
    r=other["buyer_query_receipt"]
    r["execution_identity"]="tr-other"
    r["response_hash"]=other["terminal_response"]["response_hash"]
    r["response_text"]=other["terminal_response"]["response_text"]
    other["terminal_response_id"]="tr-other"
    other["terminal_response_hash"]=other["terminal_response"]["response_hash"]
    other.pop("home_response_hash",None)
    other["home_response_hash"]=digest(other)
    return other


def test_paid_home_response_verifies():
    assert verify_home_response(paid_response())


def test_paid_home_response_requires_payment_reference():
    value=paid_response(); value["payment_reference"]=None
    value.pop("home_response_hash",None); value["home_response_hash"]=digest(value)
    assert not verify_home_response(value)


def test_paid_reconcile_creates_one_execution_index_and_exact_retry_is_idempotent(tmp_path: Path):
    response=paid_response(); state=tmp_path/"market-state"; seed_purchase(state,response)
    source=tmp_path/"paid-response.json"; source.write_text(json.dumps(response,sort_keys=True,indent=2)+"\n")
    first=reconcile_response(response_path=source,state_root=state)
    second=reconcile_response(response_path=source,state_root=state)
    assert first["new_receipt"] is True
    assert second["new_receipt"] is False
    assert first["commerce_execution_ledger"]["purchase_execution_index"]=="CREATED"
    assert second["commerce_execution_ledger"]["purchase_execution_index"]=="IDEMPOTENT_REPLAY"
    index=state/"state/commerce/execution-by-purchase"/f"{purchase_key(response['purchase_id'])}.json"
    row=json.loads(index.read_text())
    assert row["execution_id"]==response["buyer_query_receipt"]["execution_identity"]
    assert row["result_sha256"]==response["buyer_query_receipt"]["response_hash"]


def test_second_different_response_for_same_query_is_blocked_by_create_only_receipt(tmp_path: Path):
    response=paid_response(); state=tmp_path/"market-state"; seed_purchase(state,response)
    source=tmp_path/"paid-response.json"; source.write_text(json.dumps(response,sort_keys=True,indent=2)+"\n")
    reconcile_response(response_path=source,state_root=state)
    other=alternate_execution(response)
    second=tmp_path/"paid-response-other.json"; second.write_text(json.dumps(other,sort_keys=True,indent=2)+"\n")
    with pytest.raises(HomeResponseError,match="R1B_MARKET_RECEIPT_CREATE_ONLY_CONFLICT"):
        reconcile_response(response_path=second,state_root=state)


def test_second_execution_identity_for_same_paid_purchase_is_blocked_by_shared_ledger(tmp_path: Path):
    response=paid_response(); state=tmp_path/"market-state"; seed_purchase(state,response)
    persist_paid_home_response(state,response)
    other=alternate_execution(response)
    with pytest.raises(LedgerConflict):
        persist_paid_home_response(state,other)
