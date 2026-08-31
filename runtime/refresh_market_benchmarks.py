#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BenchmarkRefreshError(ValueError):
    pass


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"user-agent": "JANUS-MACHINE-MARKET/benchmark-refresh"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    text = html.unescape(raw)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def parse_exa(text: str) -> float:
    m = re.search(r"Search\s*\$\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*1k\s+requests", text, flags=re.I)
    if not m:
        m = re.search(r"Base price[^$]{0,120}\$\s*([0-9]+(?:\.[0-9]+)?)", text, flags=re.I)
    if not m:
        raise BenchmarkRefreshError("EXA_PRICE_PARSE_FAILED")
    return float(m.group(1)) / 1000.0


def parse_tavily(text: str) -> float:
    m = re.search(r"Pay-As-You-Go[^$]{0,240}\$\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*Credit", text, flags=re.I)
    if not m:
        m = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*Credit", text, flags=re.I)
    if not m:
        raise BenchmarkRefreshError("TAVILY_PRICE_PARSE_FAILED")
    return float(m.group(1))


def parse_openai(text: str) -> float:
    m = re.search(r"Web Search[^$]{0,180}\$\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*1K\s+web\s+runs", text, flags=re.I)
    if not m:
        raise BenchmarkRefreshError("OPENAI_WEB_SEARCH_PRICE_PARSE_FAILED")
    return float(m.group(1)) / 1000.0


ADAPTERS = {
    "Exa": parse_exa,
    "Tavily": parse_tavily,
    "OpenAI": parse_openai,
}


def refresh(snapshot: dict[str, Any], *, now: str, fetcher=fetch_text) -> tuple[dict[str, Any], dict[str, Any]]:
    out = json.loads(json.dumps(snapshot))
    successes = []
    failures = []
    for row in out.get("comparables") or []:
        provider = str(row.get("provider") or "")
        parser = ADAPTERS.get(provider)
        if parser is None:
            failures.append({"provider": provider, "reason": "NO_ADAPTER"})
            continue
        try:
            text = fetcher(str(row["source"]))
            value = parser(text)
            if value <= 0:
                raise BenchmarkRefreshError("NON_POSITIVE_PRICE")
            row["usd_per_unit"] = value
            row["verified_at"] = now
            successes.append({"provider": provider, "usd_per_unit": value})
        except Exception as exc:  # noqa: BLE001
            failures.append({"provider": provider, "reason": type(exc).__name__ + ":" + str(exc)})
    if successes:
        out["as_of"] = now
        out["status"] = "PARTIAL_REFRESH" if failures else "LIVE_REFRESH_ALL_ADAPTERS_PASS"
        comparable = [float(r["usd_per_unit"]) for r in out.get("comparables") or [] if "JANUS.SEARCH" in (r.get("comparable_to") or [])]
        if comparable:
            low = min(comparable)
            ceiling = max(1, int(low * 0.85 * 1_000_000))
            out.setdefault("derived", {}).setdefault("JANUS.SEARCH", {})
            out["derived"]["JANUS.SEARCH"].update({
                "lowest_comparable_usd_per_unit": low,
                "competitive_ceiling_fraction": 0.85,
                "competitive_ceiling_usdt_atomic": ceiling,
                "suggested_shadow_price_usdt_atomic": max(1, ceiling - 50),
                "suggested_shadow_price_usdt": f"{max(1, ceiling - 50) / 1_000_000:.6f}",
            })
    receipt = {
        "schema": "janus.machine_market.market_benchmark_refresh_receipt.v1",
        "refreshed_at": now,
        "successes": successes,
        "failures": failures,
        "snapshot_changed": bool(successes),
        "automatic_price_raise_authority": False,
        "failed_provider_overwrites_last_verified_price": False,
    }
    return out, receipt


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='pricing/MARKET_BENCHMARKS.json')
    parser.add_argument('--output',required=True)
    parser.add_argument('--receipt',required=True)
    parser.add_argument('--now')
    args=parser.parse_args()
    now=args.now or datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    snapshot=json.loads(Path(args.input).read_text(encoding='utf-8'))
    refreshed,receipt=refresh(snapshot,now=now)
    Path(args.output).write_text(json.dumps(refreshed,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    Path(args.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
