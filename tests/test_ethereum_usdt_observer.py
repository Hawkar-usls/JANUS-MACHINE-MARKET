from runtime.commerce_authority import USDT_ETHEREUM, build_quote
from runtime.ethereum_usdt_observer import TRANSFER_TOPIC0, address_topic, observe_from_logs

RECEIVER = "0x7149081aea54fbef57effeb52a5a966b81cc03a0"
SENDER = "0x" + "12" * 20
TX1 = "0x" + "ab" * 32
TX2 = "0x" + "ac" * 32
BLOCK_HASH = "0x" + "cd" * 32


def request():
    return {"schema": "janus.machine_market.request.v1", "sku": "JANUS.SEARCH", "input": {"query": "test"}}


def quote():
    return build_quote(request=request(), sku="JANUS.SEARCH", amount_usdt_micros=50_000, receiving_address=RECEIVER, expires_at="2026-09-01T00:00:00+00:00", nonce="n", policy_version="v1")


def topic(addr):
    return address_topic(addr)


def log(*, tx=TX1, idx=3, amount=50_000, to=RECEIVER, block=100, block_hash=BLOCK_HASH, removed=False, token=USDT_ETHEREUM):
    return {
        "address": token,
        "topics": [TRANSFER_TOPIC0, topic(SENDER), topic(to)],
        "data": hex(amount),
        "blockNumber": hex(block),
        "blockHash": block_hash,
        "transactionHash": tx,
        "logIndex": hex(idx),
        "removed": removed,
    }


def test_exact_transfer_becomes_confirmed_after_12_blocks():
    r = observe_from_logs(quote=quote(), logs=[log()], latest_block=111, canonical_block_hash=BLOCK_HASH)
    assert r["status"] == "CONFIRMED"
    assert r["confirmations"] == 12
    assert r["payment_reference"] == f"{TX1}:3"


def test_11_confirmations_stays_observed():
    r = observe_from_logs(quote=quote(), logs=[log()], latest_block=110, canonical_block_hash=BLOCK_HASH)
    assert r["status"] == "OBSERVED"
    assert r["confirmations"] == 11


def test_wrong_amount_is_not_selected():
    r = observe_from_logs(quote=quote(), logs=[log(amount=49_999)], latest_block=120)
    assert r["status"] == "NOT_FOUND"


def test_removed_reorg_log_is_not_selected():
    r = observe_from_logs(quote=quote(), logs=[log(removed=True)], latest_block=120)
    assert r["status"] == "NOT_FOUND"


def test_noncanonical_block_hash_is_quarantined():
    other = "0x" + "ee" * 32
    r = observe_from_logs(quote=quote(), logs=[log()], latest_block=120, canonical_block_hash=other)
    assert r["status"] == "QUARANTINED"
    assert r["reason"] == "BLOCK_HASH_NOT_CANONICAL"


def test_multiple_exact_transfers_are_quarantined_not_arbitrarily_selected():
    r = observe_from_logs(quote=quote(), logs=[log(), log(tx=TX2, idx=4)], latest_block=120)
    assert r["status"] == "QUARANTINED"
    assert r["reason"] == "AMBIGUOUS_MULTIPLE_EXACT_TRANSFERS"
    assert r["candidate_payment_references"] == [f"{TX1}:3", f"{TX2}:4"]


def test_same_transaction_two_transfer_logs_have_distinct_payment_identity():
    r = observe_from_logs(quote=quote(), logs=[log(idx=3), log(idx=4)], latest_block=120)
    assert r["status"] == "QUARANTINED"
    assert r["candidate_payment_references"] == [f"{TX1}:3", f"{TX1}:4"]
