from __future__ import annotations

import unittest

from runtime.r2_quote import build_quote


def request():
    return {
        "schema": "janus.machine_market.quote_request.v1",
        "sku": "JANUS.SEARCH",
        "buyer_actor_id": "github:test-agent",
        "request_id": "issue:123",
        "input": {
            "message_text": "Найди релевантные данные по этой теме.",
            "conversation_id": "quote-test",
            "turn_index": 0,
        },
        "created_at": "2026-08-31T07:00:00Z",
    }


def price(live: bool):
    return {
        "schema": "janus.machine_market.price.v1",
        "sku": "JANUS.SEARCH",
        "status": "PUBLISHED" if live else "PRICE_NOT_PUBLISHED",
        "asset": "USDT",
        "network": "ethereum-mainnet",
        "amount_atomic": 250000 if live else None,
        "decimals": 6,
        "buyer_query_turns": 1,
        "max_message_utf8_bytes": 8000,
        "max_answer_utf8_bytes": 12000,
        "conversation_history_turns": 8,
        "machine_purchase_enabled": live,
    }


def route(live: bool):
    return {
        "schema": "janus.machine_market.payment_route.v1",
        "route_id": "JANUS_USDT_ETHEREUM_MAINNET_V1",
        "network": {"name": "Ethereum Mainnet", "chain_id": 1},
        "asset": {
            "symbol": "USDT",
            "standard": "ERC20",
            "contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "decimals": 6,
        },
        "merchant": {"receiving_address": "0x7149081aea54fbef57effeb52a5a966b81cc03a0"},
        "verification": {"minimum_confirmations": 12, "rpc_quorum": 2},
        "live_payment_enabled": live,
    }


class QuoteTest(unittest.TestCase):
    def test_unpublished_price_returns_unavailable_not_fake_quote(self):
        q = build_quote(request(), price=price(False), route=route(False))
        self.assertEqual(q["status"], "UNAVAILABLE")
        self.assertIsNone(q["price"])
        self.assertIsNone(q["payment_challenge"])

    def test_live_quote_is_deterministic_and_exact_bound(self):
        a = build_quote(request(), price=price(True), route=route(True))
        b = build_quote(request(), price=price(True), route=route(True))
        self.assertEqual(a, b)
        self.assertEqual(a["status"], "QUOTED")
        self.assertEqual(a["price"]["amount_atomic"], 250000)
        self.assertEqual(a["payment_challenge"]["amount_atomic"], 250000)
        self.assertEqual(a["payment_challenge"]["to_address"], "0x7149081aea54fbef57effeb52a5a966b81cc03a0")
        self.assertIn("QUOTE_IS_NOT_PURCHASE_GRANT", a["reasons"])

    def test_request_change_changes_quote_identity(self):
        a = build_quote(request(), price=price(True), route=route(True))
        other = request()
        other["input"]["message_text"] = "Другой запрос"
        b = build_quote(other, price=price(True), route=route(True))
        self.assertNotEqual(a["request_hash"], b["request_hash"])
        self.assertNotEqual(a["quote_id"], b["quote_id"])


if __name__ == "__main__":
    unittest.main()
