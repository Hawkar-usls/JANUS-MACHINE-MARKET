from runtime.commerce_authority import USDT_ETHEREUM, build_quote
from runtime.ethereum_usdt_observer import TRANSFER_TOPIC0, address_topic, observe_transaction

RECEIVER = "0x7149081aea54fbef57effeb52a5a966b81cc03a0"
SENDER = "0x" + "12" * 20
TX = "0x" + "ab" * 32
BLOCK_HASH = "0x" + "cd" * 32


def request():
    return {"schema": "janus.machine_market.request.v1", "sku": "JANUS.SEARCH", "input": {"query": "test"}}


def quote():
    return build_quote(request=request(), sku="JANUS.SEARCH", amount_usdt_micros=50_000, receiving_address=RECEIVER, expires_at="2026-09-04T12:15:00+00:00", nonce="n", policy_version="v1")


def log(*, idx=3, amount=50_000, to=RECEIVER, token=USDT_ETHEREUM):
    return {
        "address": token,
        "topics": [TRANSFER_TOPIC0, address_topic(SENDER), address_topic(to)],
        "data": hex(amount),
        "blockNumber": hex(100),
        "blockHash": BLOCK_HASH,
        "transactionHash": TX,
        "logIndex": hex(idx),
        "removed": False,
    }


class FakeRpc:
    def __init__(self, *, status=1, logs=None, latest=111, canonical_hash=BLOCK_HASH, timestamp=1_788_520_000):
        self.status=status; self.logs=list(logs if logs is not None else [log()]); self.latest=latest; self.canonical_hash=canonical_hash; self.timestamp=timestamp
    def call(self, method, params):
        if method == "eth_chainId": return hex(1)
        if method == "eth_blockNumber": return hex(self.latest)
        if method == "eth_getTransactionReceipt":
            return {"transactionHash": TX, "status": hex(self.status), "logs": self.logs}
        if method == "eth_getBlockByNumber":
            return {"hash": self.canonical_hash, "timestamp": hex(self.timestamp)}
        raise AssertionError(method)


def test_exact_transaction_receipt_confirms_specific_log():
    r=observe_transaction(FakeRpc(), quote(), tx_hash=TX, expected_log_index=3)
    assert r["status"]=="CONFIRMED"
    assert r["payment_reference"]==f"{TX}:3"
    assert r["confirmations"]==12
    assert r["block_timestamp"].endswith("Z")


def test_wrong_log_index_is_not_found():
    r=observe_transaction(FakeRpc(), quote(), tx_hash=TX, expected_log_index=9)
    assert r["status"]=="NOT_FOUND"


def test_reverted_transaction_is_quarantined():
    r=observe_transaction(FakeRpc(status=0), quote(), tx_hash=TX, expected_log_index=3)
    assert r["status"]=="QUARANTINED"
    assert r["reason"]=="TRANSACTION_REVERTED"


def test_wrong_amount_does_not_count_as_payment():
    r=observe_transaction(FakeRpc(logs=[log(amount=49_999)]), quote(), tx_hash=TX, expected_log_index=3)
    assert r["status"]=="NOT_FOUND"


def test_two_exact_logs_without_index_are_quarantined():
    r=observe_transaction(FakeRpc(logs=[log(idx=3),log(idx=4)]), quote(), tx_hash=TX)
    assert r["status"]=="QUARANTINED"
    assert r["reason"]=="AMBIGUOUS_MULTIPLE_EXACT_TRANSFERS"


def test_noncanonical_transaction_block_is_quarantined():
    other="0x"+"ee"*32
    r=observe_transaction(FakeRpc(canonical_hash=other), quote(), tx_hash=TX, expected_log_index=3)
    assert r["status"]=="QUARANTINED"
    assert r["reason"]=="BLOCK_HASH_NOT_CANONICAL"
