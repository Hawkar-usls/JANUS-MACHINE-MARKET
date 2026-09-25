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
chooser = (ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text(encoding="utf-8")

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
names = {
    (((row or {}).get("item") or {}).get("name"))
    for row in (data.get("itemListElement") or [])
}
require(names == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "AGENT_LANDING_JSONLD_SERVICE_SET_DRIFT")

require("Content-Signal: search=yes, ai-input=yes" in robots, "ROBOTS_AI_SEARCH_SIGNAL_DRIFT")
require("Sitemap: https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/sitemap.xml" in robots, "ROBOTS_SITEMAP_DRIFT")

require("Gate Check Only" in paid, "PAID_TEMPLATE_GATE_LABEL_DRIFT")
require("CURRENT DEFAULT: GATED" in paid, "PAID_TEMPLATE_GATE_WARNING_DRIFT")
require("JANUS for Autonomous Agents" in chooser, "ISSUE_CHOOSER_AGENT_LINK_MISSING")
require("Machine-readable API index" in chooser, "ISSUE_CHOOSER_API_LINK_MISSING")

print("JANUS_WEB_DISCOVERY_INTEGRITY_PASS")
print("PUBLIC_WEB_SERVICES=JANUS.SEARCH,JANUS.PR_REVIEW")
print("SITEMAP_XML_VALID=TRUE")
print("AGENT_JSONLD_VALID=TRUE")
print("PAID_TEMPLATE_DEFAULT_GATED=TRUE")
