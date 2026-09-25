import json
import unittest

from runtime.telegram_gateway_guard import (
    TelegramGatewayError,
    evaluate_abuse_gate,
    machine_signature,
    normalize_telegram_update,
    verify_machine_request,
    verify_telegram_webhook_secret,
)

class TelegramGatewayGuardTests(unittest.TestCase):
    def test_webhook_secret_required_and_constant_time_comparable(self):
        verify_telegram_webhook_secret("abc_123", "abc_123")
        with self.assertRaisesRegex(TelegramGatewayError, "SECRET_INVALID"):
            verify_telegram_webhook_secret("wrong", "abc_123")

    def test_private_telegram_human_is_normalized(self):
        update={"update_id":44,"message":{"message_id":8,"chat":{"id":77,"type":"private"},"from":{"id":99,"is_bot":False},"text":"find public sonar datasets"}}
        r=normalize_telegram_update(update)
        self.assertEqual(r["principal_id"],"telegram:user:99")
        self.assertEqual(r["idempotency_key"],"telegram-update:44")
        self.assertEqual(r["principal_kind"],"HUMAN")

    def test_edited_or_group_order_is_denied(self):
        with self.assertRaisesRegex(TelegramGatewayError,"EDITED"):
            normalize_telegram_update({"update_id":1,"edited_message":{},"message":{}})
        with self.assertRaisesRegex(TelegramGatewayError,"PRIVATE_CHAT"):
            normalize_telegram_update({"update_id":2,"message":{"message_id":1,"chat":{"id":1,"type":"group"},"from":{"id":2},"text":"x"}})

    def test_machine_hmac_timestamp_nonce_and_hop(self):
        body=json.dumps({"idempotency_key":"ord-1","sku":"JANUS.SEARCH","text":"x"},separators=(",",":")).encode()
        ts=1770000000; key=b"secret"; nonce="n-1"; kid="agent-a"
        sig=machine_signature(key=key,key_id=kid,timestamp=ts,nonce=nonce,body=body,hop_count=0)
        r=verify_machine_request(body=body,key_id=kid,timestamp=ts,nonce=nonce,signature=sig,hop_count=0,keys={kid:key},now=ts)
        self.assertEqual(r["principal_id"],"machine:key:agent-a")
        with self.assertRaisesRegex(TelegramGatewayError,"NONCE_REPLAY"):
            verify_machine_request(body=body,key_id=kid,timestamp=ts,nonce=nonce,signature=sig,hop_count=0,keys={kid:key},seen_nonces=[nonce],now=ts)
        with self.assertRaisesRegex(TelegramGatewayError,"HOP_LIMIT"):
            verify_machine_request(body=body,key_id=kid,timestamp=ts,nonce="n2",signature="x",hop_count=2,keys={kid:key},now=ts)

    def test_first_free_only_once_and_idempotent_retry_not_second_order(self):
        first=evaluate_abuse_gate(principal_id="telegram:user:9",idempotency_key="u9-1",seen_idempotency={},principals_with_free_search=[],active_principals=[],last_order_unix={},now=1000,sku="JANUS.SEARCH",global_first_free_today=0)
        self.assertEqual(first["reason"],"FIRST_FREE_SEARCH_ADMITTED")
        replay=evaluate_abuse_gate(principal_id="telegram:user:9",idempotency_key="u9-1",seen_idempotency={"u9-1":{"order_id":"o1"}},principals_with_free_search=["telegram:user:9"],active_principals=[],last_order_unix={},now=1001,sku="JANUS.SEARCH",global_first_free_today=1)
        self.assertTrue(replay["replay"])
        with self.assertRaisesRegex(TelegramGatewayError,"FIRST_FREE_SEARCH_ALREADY_USED"):
            evaluate_abuse_gate(principal_id="telegram:user:9",idempotency_key="u9-2",seen_idempotency={},principals_with_free_search=["telegram:user:9"],active_principals=[],last_order_unix={},now=2000,sku="JANUS.SEARCH",global_first_free_today=1)

    def test_specialist_skus_remain_gated(self):
        with self.assertRaisesRegex(TelegramGatewayError,"SPECIALIST_SKU_NOT_PUBLIC_LIVE"):
            evaluate_abuse_gate(principal_id="machine:key:x",idempotency_key="x1",seen_idempotency={},principals_with_free_search=[],active_principals=[],last_order_unix={},now=1000,sku="JANUS.TOPA_HUNT",global_first_free_today=0)

if __name__ == "__main__":
    unittest.main()
