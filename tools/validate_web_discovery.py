#!/usr/bin/env python3
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def require(ok, code):
    if not ok:
        raise SystemExit(code)

main = (ROOT / "index.html").read_text(encoding="utf-8")
agents = (ROOT / "agents/index.html").read_text(encoding="utf-8")
sitemap_text = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
paid = (ROOT / ".github/ISSUE_TEMPLATE/janus-paid-search.md").read_text(encoding="utf-8")
btt_paid = (ROOT / ".github/ISSUE_TEMPLATE/janus-paid-search-btt.md").read_text(encoding="utf-8")
chooser = (ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text(encoding="utf-8")
readiness = json.loads((ROOT / "COMMERCE_READINESS.json").read_text(encoding="utf-8"))
ingress = json.loads((ROOT / "MACHINE_INGRESS.json").read_text(encoding="utf-8"))
btt_route = json.loads((ROOT / "BTT_PAYMENT_ROUTE.json").read_text(encoding="utf-8"))
witness = json.loads((ROOT / "FOREIGN_AGENT_WITNESS.json").read_text(encoding="utf-8"))

require("\\n" not in sitemap_text, "SITEMAP_LITERAL_BACKSLASH_N")
try:
    root = ET.fromstring(sitemap_text)
except ET.ParseError as exc:
    raise SystemExit(f"SITEMAP_XML_INVALID:{exc}") from exc

ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
urls = {x.text for x in root.findall("s:url/s:loc", ns) if x.text}
required_urls = {
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/",
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/agents/",
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/apis.json",
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/discovery/GITHUB_ISSUES_INGRESS.openapi.json",
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/discovery/PR_REVIEW_GITHUB_INGRESS.openapi.json",
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/.well-known/agent-skills/index.json",
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/.well-known/agent-skills/janus-search/SKILL.md",
    "https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/.well-known/agent-skills/janus-pr-review/SKILL.md",
}
require(required_urls <= urls, "SITEMAP_REQUIRED_AGENT_URL_MISSING")

for token in (
    '<link rel="canonical" href="https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/">',
    'property="og:title"',
    '"@type":"WebSite"',
    'JANUS.SEARCH',
    'JANUS.PR_REVIEW',
):
    require(token in main, f"MAIN_DISCOVERY_METADATA_DRIFT:{token}")

for token in (
    "TWO LIVE PUBLIC INGRESS PATHS",
    "JANUS.SEARCH",
    "JANUS.PR_REVIEW",
    "FIRST SEARCH FREE",
    "FIRST PR REVIEW FREE",
    "PR REVIEW OpenAPI",
    "Agent Skills",
    "target repository code is never executed",
):
    require(token in agents, f"AGENT_LANDING_DRIFT:{token}")

match = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', agents, re.S)
require(match is not None, "AGENT_LANDING_JSONLD_MISSING")
try:
    data = json.loads(match.group(1))
except json.JSONDecodeError as exc:
    raise SystemExit(f"AGENT_LANDING_JSONLD_INVALID:{exc}") from exc
require(data.get("@type") == "ItemList", "AGENT_LANDING_JSONLD_TYPE_DRIFT")
names = {(((row or {}).get("item") or {}).get("name")) for row in (data.get("itemListElement") or [])}
require(names == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "AGENT_LANDING_JSONLD_SERVICE_SET_DRIFT")

require("Content-Signal: search=yes, ai-input=yes" in robots, "ROBOTS_AI_SEARCH_SIGNAL_DRIFT")
require("Sitemap: https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/sitemap.xml" in robots, "ROBOTS_SITEMAP_DRIFT")

require("JANUS Paid Search — Live Checkout" in paid, "PAID_TEMPLATE_LIVE_LABEL_DRIFT")
require("LIVE PAID JANUS.SEARCH" in paid, "PAID_TEMPLATE_LIVE_WARNING_DRIFT")
require("JANUS_PAID_SEARCH_JSON" in paid, "PAID_TEMPLATE_REQUEST_MARKER_MISSING")
require("USDT on Ethereum mainnet" in paid, "PAID_TEMPLATE_USDT_ROUTE_MISSING")
require("JANUS Paid Search — BTT / TRON Live Checkout" in btt_paid, "BTT_TEMPLATE_LIVE_LABEL_DRIFT")
require("JANUS_PAID_SEARCH_BTT_JSON" in btt_paid, "BTT_TEMPLATE_REQUEST_MARKER_MISSING")
require("BTTCUSDT" in btt_paid, "BTT_TEMPLATE_ORACLE_MARKET_MISSING")
require("BitTorrent Token" in btt_paid, "BTT_TEMPLATE_PAYMENT_ASSET_MISSING")

require(readiness.get("seller_commerce_authorized") is True, "WEB_SELLER_AUTHORIZATION_FALSE")
require(readiness.get("money_enabled") is True, "WEB_PAID_SEARCH_MONEY_DISABLED")
paid_ingress = ((ingress.get("live_services") or {}).get("JANUS.SEARCH") or {}).get("paid_checkout") or {}
require(paid_ingress.get("status") == "LIVE_JANUS_SEARCH_DUAL_RAIL_ONLY", "WEB_PAID_SEARCH_INGRESS_NOT_DUAL_RAIL_LIVE")
require(paid_ingress.get("primary_payment_state") == "LIVE_EXACT_INVOICE", "WEB_USDT_EXACT_INVOICE_NOT_LIVE")
require(paid_ingress.get("alternative_payment_state") == "LIVE_EXACT_INVOICE", "WEB_BTT_EXACT_INVOICE_NOT_LIVE")
routes = paid_ingress.get("payment_routes") or {}
require((routes.get("USDT_ETHEREUM") or {}).get("status") == "LIVE_EXACT_INVOICE", "WEB_USDT_ROUTE_NOT_LIVE")
btt = routes.get("BTT_TRON") or {}
require(btt.get("status") == "LIVE_EXACT_INVOICE", "WEB_BTT_ROUTE_NOT_LIVE")
require(btt.get("asset") == "BTT", "WEB_BTT_ASSET_DRIFT")
require(btt.get("exchange_ticker") == "BTTC", "WEB_BTT_TICKER_DRIFT")
require(btt.get("exchange_market_symbol") == "BTTCUSDT", "WEB_BTT_MARKET_DRIFT")
require((btt_route.get("pricing") or {}).get("live_quote_allowed") is True, "WEB_BTT_QUOTE_NOT_LIVE")
require((btt_route.get("settlement") or {}).get("observer") == "runtime/tron_btt_observer.py", "WEB_BTT_OBSERVER_DRIFT")
require(paid_ingress.get("foreign_agent_witness_is_seller_prerequisite") is False, "WEB_WITNESS_REINTRODUCED_AS_SELLER_GATE")
require(witness.get("foreign_agent_witness") is False, "WEB_DISCOVERY_MUST_NOT_FABRICATE_WITNESS")
require("JANUS for Autonomous Agents" in chooser, "ISSUE_CHOOSER_AGENT_LINK_MISSING")
require("Machine-readable API index" in chooser, "ISSUE_CHOOSER_API_LINK_MISSING")

print("JANUS_WEB_DISCOVERY_INTEGRITY_PASS")
print("PUBLIC_WEB_SERVICES=JANUS.SEARCH,JANUS.PR_REVIEW")
print("SITEMAP_XML_VALID=TRUE")
print("AGENT_JSONLD_VALID=TRUE")
print("PAID_SEARCH_USDT_EXACT_INVOICE_LIVE=TRUE")
print("PAID_SEARCH_BTT_EXACT_INVOICE_LIVE=TRUE")
print("BTT_PAYMENT_ASSET=BTT")
print("BTT_EXCHANGE_MARKET=BTTCUSDT")
print("FOREIGN_AGENT_WITNESS=FALSE_PENDING_REAL_EVIDENCE")
