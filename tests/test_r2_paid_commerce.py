from __future__ import annotations

import unittest

from runtime.r2_erc20_payment import PaymentVerificationError, TRANSFER_TOPIC, digest, parse_exact_transfer
from runtime.r2_paid_buyer_query import PaidBuyerQueryError, build_paid_packet

TOKEN = "0xdac17f958d2ee523a2206206994597c13d831ec7"
MERCHANT = "0x7149081aea54fbef57effeb52a5a966b81cc03a0"
BUYER = "0x1111111111111111111111111111111111111111"
TX = "0x" + "ab" * 32
BLOCK_HASH = "0x" + "cd" * 32
AMOUNT = 1_000_000


def topic(address: str) -> str:
    return "0x" + "0" * 24 + address.lower()[2:]


def chain_receipt(amount: int = AMOUNT, to: str = MERCHANT, status: str = "0x1"):
    return {
        "transactionHash": TX,
        "status": status,
        "blockHash": BLOCK_HASH,
        "blockNumber": hex(100),
        "logs": [{
            "address": TOKEN,
            "topics": [TRANSFER_TOPIC, topic(BUYER), topic(to)],
            "data": hex(amount),
            "logIndex": "0x7",
        }],
    }


def route(active: bool = True):
    return {
        "schema": "janus.machine_market.payment_route.v1",
        "route_id": "JANUS_USDT_ETHEREUM_MAINNET_V1",
        "network": {"name": "Ethereum Mainnet", "chain_id": 1},
        "asset": {"symbol": "USDT", "standard": "ERC20", "contract": TOKEN, "decimals": 6},
        "merchant": {"receiving_address": MERCHANT},
        "verification": {"minimum_confirmations": 12, "rpc_quorum": 2},
        "live_payment_enabled": active,
    }


def price(enabled: bool = True):
    return {
        "schema": "janus.machine_market.price.v1",
        "sku": "JANUS.SEARCH",
        "status": "PUBLISHED" if enabled else "PRICE_NOT_PUBLISHED",
        "asset": "USDT",
        "network": "ethereum-mainnet",
        "amount_atomic": AMOUNT if enabled else None,
        "decimals": 6,
        "buyer_query_turns": 1,
        "max_message_utf8_bytes": 8000,
        "max_answer_utf8_bytes": 12000,
        "conversation_history_turns": 8,
        "machine_purchase_enabled": enabled,
    }


def payment_receipt():
    value = {
        "schema": "janus.machine_market.payment_receipt.v1",
        "route_id": "JANUS_USDT_ETHEREUM_MAINNET_V1",
        "chain_id": 1,
        "asset": "USDT",
        "token_contract": TOKEN,
        "tx_hash": TX,
        "block_hash": BLOCK_HASH,
        "block_number": 100,
        "log_index": 7,
        "from_address": BUYER,
        "to_address": MERCHANT,
        "amount_atomic": AMOUNT,
        "confirmations": 21,
        "rpc_quorum": 2,
        "rpc_provider_count": 2,
        "verification_status": "VERIFIED_EXACT_ERC20_TRANSFER",
        "payment_reference": f"ethereum:1:{TX}:7",
    }
    value["receipt_hash"] = digest(value)
    return value


def request():
    return {
        "schema": "janus.machine_market.paid_buyer_query_request.v1",
        "request_id": "github-issue-id:999",
        "buyer_actor_id": "github:foreign-agent",
        "conversation_id": "paid-999",
        "turn_index": 0,
        "message_text": "Проведи bounded поиск и верни результат.",
        "created_at": "2026-08-31T07:00:00Z",
        "tx_hash": TX,
        "source_issue_number": 999,
        "source_issue_id": 999999,
        "request_origin": "FOREIGN_MACHINE_PURCHASE",
    }


class ExactPaymentTest(unittest.TestCase):
    def test_exact_transfer_passes(self):
        e = parse_exact_transfer(
            receipt=chain_receipt(),
            current_block=120,
            tx_hash=TX,
            token_contract=TOKEN,
            expected_to=MERCHANT,
            expected_amount_atomic=AMOUNT,
            minimum_confirmations=12,
        )
        self.assertEqual(e.amount_atomic, AMOUNT)
        self.assertEqual(e.to_address, MERCHANT)
        self.assertEqual(e.log_index, 7)
        self.assertEqual(e.confirmations, 21)

    def test_wrong_amount_fails(self):
        with self.assertRaisesRegex(PaymentVerificationError, "EXACT_ERC20_TRANSFER_MATCH_COUNT_NOT_ONE"):
            parse_exact_transfer(
                receipt=chain_receipt(amount=AMOUNT - 1),
                current_block=120,
                tx_hash=TX,
                token_contract=TOKEN,
                expected_to=MERCHANT,
                expected_amount_atomic=AMOUNT,
                minimum_confirmations=12,
            )

    def test_wrong_recipient_fails(self):
        with self.assertRaisesRegex(PaymentVerificationError, "EXACT_ERC20_TRANSFER_MATCH_COUNT_NOT_ONE"):
            parse_exact_transfer(
                receipt=chain_receipt(to="0x2222222222222222222222222222222222222222"),
                current_block=120,
                tx_hash=TX,
                token_contract=TOKEN,
                expected_to=MERCHANT,
                expected_amount_atomic=AMOUNT,
                minimum_confirmations=12,
            )

    def test_failed_transaction_fails(self):
        with self.assertRaisesRegex(PaymentVerificationError, "TX_RECEIPT_NOT_SUCCESS"):
            parse_exact_transfer(
                receipt=chain_receipt(status="0x0"),
                current_block=120,
                tx_hash=TX,
                token_contract=TOKEN,
                expected_to=MERCHANT,
                expected_amount_atomic=AMOUNT,
                minimum_confirmations=12,
            )

    def test_insufficient_confirmations_fails(self):
        with self.assertRaisesRegex(PaymentVerificationError, "PAYMENT_CONFIRMATIONS_INSUFFICIENT"):
            parse_exact_transfer(
                receipt=chain_receipt(),
                current_block=105,
                tx_hash=TX,
                token_contract=TOKEN,
                expected_to=MERCHANT,
                expected_amount_atomic=AMOUNT,
                minimum_confirmations=12,
            )


class PaidPacketTest(unittest.TestCase):
    def test_paid_packet_is_deterministic_and_non_authoritative(self):
        a = build_paid_packet(request(), price=price(), route=route(), payment_receipt=payment_receipt())
        b = build_paid_packet(request(), price=price(), route=route(), payment_receipt=payment_receipt())
        self.assertEqual(a["packet_hash"], b["packet_hash"])
        self.assertEqual(a["query_id"], b["query_id"])
        self.assertEqual(a["purchase_grant"]["purchase_id"], b["purchase_grant"]["purchase_id"])
        self.assertTrue(a["money_enabled"])
        self.assertTrue(a["production_purchase"])
        self.assertFalse(a["execution_authority_granted"])
        self.assertFalse(a["command_authority_granted"])
        self.assertFalse(a["external_effect_authorized"])
        self.assertEqual(a["purchase_grant"]["payment_reference"], payment_receipt()["payment_reference"])

    def test_disabled_price_fails_closed(self):
        with self.assertRaisesRegex(PaidBuyerQueryError, "R2_PRICE_NOT_PUBLISHED"):
            build_paid_packet(request(), price=price(False), route=route(), payment_receipt=payment_receipt())

    def test_disabled_route_fails_closed(self):
        with self.assertRaisesRegex(PaidBuyerQueryError, "R2_LIVE_PAYMENT_ROUTE_NOT_ENABLED"):
            build_paid_packet(request(), price=price(), route=route(False), payment_receipt=payment_receipt())

    def test_wrong_payment_amount_fails(self):
        p = payment_receipt()
        p["amount_atomic"] -= 1
        body = dict(p)
        body.pop("receipt_hash")
        p["receipt_hash"] = digest(body)
        with self.assertRaisesRegex(PaidBuyerQueryError, "R2_PAYMENT_RECEIPT_INVALID"):
            build_paid_packet(request(), price=price(), route=route(), payment_receipt=p)


if __name__ == "__main__":
    unittest.main()
