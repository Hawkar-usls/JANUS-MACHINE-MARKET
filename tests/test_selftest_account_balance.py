from __future__ import annotations

import json
import unittest

from runtime.buyer_accounts import build_event, project


class SelfTestAccountBalanceTest(unittest.TestCase):
    def test_internal_agent_gets_test_balance_and_can_spend_once(self):
        cfg=json.load(open('SELF_TEST_AGENT.json', encoding='utf-8'))
        actor=cfg['agent_id']
        e1=build_event(buyer_actor_id=actor,event_type='ACCOUNT_OPENED',event_id='selftest-open',created_at='2026-08-31T07:20:00Z',payload={},previous_event_hash=None)
        e2=build_event(buyer_actor_id=actor,event_type='MARKET_TEST_CREDIT_MINTED',event_id='selftest-mint',created_at='2026-08-31T07:20:01Z',payload={'amount':cfg['initial_test_credit'],'cash_value':False},previous_event_hash=e1['event_hash'])
        e3=build_event(buyer_actor_id=actor,event_type='MARKET_TEST_CREDIT_SPENT',event_id='selftest-order-search',created_at='2026-08-31T07:20:02Z',payload={'amount':1,'sku':'JANUS.SEARCH','production_payment_proof':False},previous_event_hash=e2['event_hash'])
        h=project([e1,e2,e3])
        self.assertEqual(h['buyer_actor_id'], actor)
        self.assertEqual(h['balances']['MARKET_TEST_CREDIT'], cfg['initial_test_credit']-1)
        self.assertFalse(cfg['cash_value'])
        self.assertFalse(cfg['production_payment_proof'])


if __name__ == '__main__':
    unittest.main()
