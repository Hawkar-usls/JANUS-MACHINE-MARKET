from __future__ import annotations

import json
import unittest
from pathlib import Path

from runtime.refresh_market_benchmarks import parse_exa, parse_openai, parse_tavily, refresh

ROOT=Path(__file__).resolve().parents[1]


class BenchmarkRefreshTest(unittest.TestCase):
    def test_provider_parsers(self):
        self.assertEqual(parse_exa('Search $7/1k requests'),0.007)
        self.assertEqual(parse_tavily('Pay-As-You-Go Plan Price: $0.008 / Credit'),0.008)
        self.assertEqual(parse_openai('Web Search (all models) $10.00 / 1K web runs'),0.01)

    def test_failed_provider_preserves_last_verified_price(self):
        snap=json.loads((ROOT/'pricing/MARKET_BENCHMARKS.json').read_text(encoding='utf-8'))
        old={r['provider']:r['usd_per_unit'] for r in snap['comparables']}
        def fake(url):
            if 'exa.ai' in url: return 'Search $8/1k requests'
            raise RuntimeError('network down')
        out,receipt=refresh(snap,now='2026-08-31T08:00:00Z',fetcher=fake)
        rows={r['provider']:r for r in out['comparables']}
        self.assertEqual(rows['Exa']['usd_per_unit'],0.008)
        self.assertEqual(rows['Tavily']['usd_per_unit'],old['Tavily'])
        self.assertEqual(rows['OpenAI']['usd_per_unit'],old['OpenAI'])
        self.assertFalse(receipt['failed_provider_overwrites_last_verified_price'])
        self.assertEqual(len(receipt['successes']),1)
        self.assertEqual(len(receipt['failures']),2)


if __name__=='__main__':
    unittest.main()
