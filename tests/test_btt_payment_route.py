from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58check_decode(value: str) -> bytes:
    n = 0
    for ch in value:
        n = n * 58 + B58.index(ch)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    pad = len(value) - len(value.lstrip("1"))
    raw = b"\x00" * pad + raw
    payload, checksum = raw[:-4], raw[-4:]
    assert hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] == checksum
    return payload

class BttPaymentRouteTests(unittest.TestCase):
    def setUp(self):
        self.route = json.loads((ROOT / "BTT_PAYMENT_ROUTE.json").read_text(encoding="utf-8"))
        self.pricing = json.loads((ROOT / "PRICING.json").read_text(encoding="utf-8"))
        self.agent = json.loads((ROOT / "AGENT_MARKET.json").read_text(encoding="utf-8"))
        self.readiness = json.loads((ROOT / "COMMERCE_READINESS.json").read_text(encoding="utf-8"))
        self.policy = (ROOT / "PAYMENT_POLICY.md").read_text(encoding="utf-8")

    def test_receiver_is_valid_tron_base58check(self):
        address = self.route["asset"]["receiver"]
        payload = b58check_decode(address)
        self.assertEqual(len(payload), 21)
        self.assertEqual(payload[0], 0x41)

    def test_btt_asset_identity_is_frozen(self):
        asset = self.route["asset"]
        self.assertEqual(asset["canonical_symbol"], "BTT")
        self.assertEqual(asset["network"], "TRON Mainnet")
        self.assertEqual(asset["token_standard"], "TRC-20")
        self.assertEqual(asset["token_contract"], "TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4")
        self.assertEqual(asset["receiver"], "TSqkDJX9uBEnA8mmRc4UN3Bw6hcujcvmd1")

    def test_discount_is_exactly_fifty_percent_of_usdt_reference(self):
        price = self.route["pricing"]
        self.assertEqual(price["discount_bps"], 5000)
        self.assertEqual(price["discount_percent"], 50)
        alt = self.pricing["alternative_payment_routes"]["BTT_TRON"]
        self.assertEqual(alt["discount_bps"], 5000)
        for micros in (50_000, 80_000, 250_000, 1_000_000):
            discounted = round(micros * (10_000 - alt["discount_bps"]) / 10_000)
            self.assertEqual(discounted, micros // 2)

    def test_route_is_declared_but_cannot_accept_live_payment_yet(self):
        self.assertFalse(self.route["pricing"]["live_quote_allowed"])
        self.assertEqual(self.route["pricing"]["btt_usd_oracle"], "NOT_IMPLEMENTED_YET")
        self.assertEqual(self.route["settlement"]["observer"], "NOT_IMPLEMENTED_YET")
        self.assertFalse(self.route["commerce_gate"]["money_enabled"])
        self.assertFalse(self.route["commerce_gate"]["live_invoice_allowed"])
        self.assertFalse(self.readiness["money_enabled"])
        self.assertEqual(
            self.readiness["alternative_payment_rails"]["BTT_TRON"]["status"],
            "DECLARED_DISCOUNT_ROUTE_GATE_CLOSED",
        )

    def test_public_manifests_and_policy_match(self):
        match = [x for x in self.agent["payment_routes"] if x["id"] == "BTT_TRON_DECLARED_DISCOUNT_RECEIVER"]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]["discount_bps"], 5000)
        self.assertEqual(match[0]["receiving_address"], self.route["asset"]["receiver"])
        self.assertIn(self.route["asset"]["receiver"], self.policy)
        self.assertIn("DO NOT SEND BTT WITHOUT AN EXACT LIVE JANUS INVOICE", self.policy)

if __name__ == "__main__":
    unittest.main()
