from datetime import datetime, timezone

import pytest

from runtime.btt_paid_search_checkout import issue_btt_invoice
from runtime.commerce_authority import CommerceInvalid, verify_payment_receipt
from runtime.tron_btt_observer import TRANSFER_TOPIC, observe_btt_transfer, tron_hex20
from tests.test_btt_paid_search_checkout import NOW, oracle, request
from tests.test_paid_search_checkout import pricing

TXID="ab"*32


class FakeTron:
    def __init__(self, body, info): self.body=body; self.info=info
    def post(self,path,body):
        if path.endswith("gettransactionbyid"): return self.body
        if path.endswith("gettransactioninfobyid"): return self.info
        raise AssertionError(path)


def fixture_info(inv, *, amount=None, duplicate=False, receipt_result="SUCCESS", contract_ret="SUCCESS"):
    q=inv["quote"]; amount=int(q["amount_atomic"] if amount is None else amount)
    receiver=tron_hex20(q["receiving_address"]); contract=tron_hex20(q["token_contract"])
    log={"address":contract,"topics":[TRANSFER_TOPIC,"0"*64,("0"*24)+receiver],"data":hex(amount)[2:].rjust(64,"0")}
    logs=[log,dict(log)] if duplicate else [log]
    body={"txID":TXID,"ret":[{"contractRet":contract_ret}]}
    info={"id":TXID,"result":"SUCCESS","receipt":{"result":receipt_result},"blockNumber":123456789,"blockTimeStamp":int((NOW.replace(minute=5)).timestamp()*1000),"log":logs}
    return body,info


def invoice(): return issue_btt_invoice(request=request(),pricing=pricing(),issued_at=NOW,oracle=oracle())


def test_exact_solidified_transfer_is_confirmed_and_receipt_verifies():
    inv=invoice(); body,info=fixture_info(inv); receipt=observe_btt_transfer(FakeTron(body,info),inv["quote"],txid=TXID,observed_at=NOW.replace(minute=6))
    assert receipt["status"]=="CONFIRMED"
    assert receipt["payment_reference"]==f"tron:{TXID}:0"
    assert receipt["event_index"]==receipt["log_index"]==0
    verify_payment_receipt(inv["quote"],receipt)


def test_wrong_atomic_amount_is_not_payment():
    inv=invoice(); body,info=fixture_info(inv,amount=inv["amount_atomic"]-1); out=observe_btt_transfer(FakeTron(body,info),inv["quote"],txid=TXID)
    assert out["status"]=="NOT_FOUND"
    assert out["reason"]=="EXACT_TRC20_TRANSFER_NOT_FOUND"


def test_duplicate_exact_transfers_are_quarantined_until_event_index_is_explicit():
    inv=invoice(); body,info=fixture_info(inv,duplicate=True); out=observe_btt_transfer(FakeTron(body,info),inv["quote"],txid=TXID)
    assert out["status"]=="QUARANTINED"
    assert out["candidate_event_indexes"]==[0,1]
    chosen=observe_btt_transfer(FakeTron(body,info),inv["quote"],txid=TXID,expected_event_index=1)
    assert chosen["status"]=="CONFIRMED" and chosen["event_index"]==1


def test_failed_smart_contract_execution_is_rejected_even_if_log_shape_exists():
    inv=invoice(); body,info=fixture_info(inv,receipt_result="OUT_OF_ENERGY")
    with pytest.raises(CommerceInvalid,match="receipt.result"):
        observe_btt_transfer(FakeTron(body,info),inv["quote"],txid=TXID)


def test_failed_transaction_body_is_rejected():
    inv=invoice(); body,info=fixture_info(inv,contract_ret="REVERT")
    with pytest.raises(CommerceInvalid,match="contractRet"):
        observe_btt_transfer(FakeTron(body,info),inv["quote"],txid=TXID)


def test_wrong_recipient_is_not_payment():
    inv=invoice(); body,info=fixture_info(inv); info["log"][0]["topics"][2]="0"*64
    out=observe_btt_transfer(FakeTron(body,info),inv["quote"],txid=TXID)
    assert out["status"]=="NOT_FOUND"
