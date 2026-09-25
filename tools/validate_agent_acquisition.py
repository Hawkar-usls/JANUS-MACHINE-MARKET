#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    p = ROOT / path
    if not p.is_file():
        raise SystemExit(f"MISSING:{path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"INVALID_JSON:{path}:{exc}") from exc

def require(ok, code):
    if not ok:
        raise SystemExit(code)

apis = load("apis.json")
well_known = load(".well-known/apis.json")
openapi = load("discovery/GITHUB_ISSUES_INGRESS.openapi.json")
pr_openapi = load("discovery/PR_REVIEW_GITHUB_INGRESS.openapi.json")
acq = load("discovery/AGENT_ACQUISITION.json")
pointer = load(".well-known/agent-market.json")
agent = load("AGENT_MARKET.json")
commerce = load("COMMERCE_READINESS.json")
witness = load("FOREIGN_AGENT_WITNESS.json")
ingress = load("MACHINE_INGRESS.json")
public_beta = load("PUBLIC_SERVICE_BETA.json")
commercial = load("COMMERCIAL.json")
readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
llms_text = (ROOT / "llms.txt").read_text(encoding="utf-8")
skill_index = load(".well-known/agent-skills/index.json")
skill_index_mirror = load("skills/index.json")

require(apis == well_known, "APIS_JSON_MIRROR_DRIFT")
require(apis.get("specificationVersion") == "0.23", "APIS_JSON_SPEC_DRIFT")
require(apis.get("type") == "Index", "APIS_JSON_TYPE_DRIFT")
require(apis.get("kind") == "opensource", "APIS_JSON_KIND_DRIFT")

require(skill_index == skill_index_mirror, "AGENT_SKILLS_INDEX_MIRROR_DRIFT")
skills = skill_index.get("skills") or []
by_name = {row.get("name"): row for row in skills}
require(set(by_name) == {"janus-search", "janus-pr-review"}, "AGENT_SKILL_SET_DRIFT")
for name in ("janus-search", "janus-pr-review"):
    live = ROOT / f".well-known/agent-skills/{name}/SKILL.md"
    mirror = ROOT / f"skills/{name}/SKILL.md"
    require(live.is_file() and mirror.is_file(), f"AGENT_SKILL_MISSING:{name}")
    require(live.read_bytes() == mirror.read_bytes(), f"AGENT_SKILL_MIRROR_DRIFT:{name}")
    actual = "sha256:" + hashlib.sha256(live.read_bytes()).hexdigest()
    require(by_name[name].get("digest") == actual, f"AGENT_SKILL_DIGEST_DRIFT:{name}")
    require(
        any(x.get("type") == "AgentSkill" and name in str(x.get("url", "")) for x in (apis.get("common") or [])),
        f"APIS_JSON_AGENT_SKILL_MISSING:{name}",
    )

entries = apis.get("apis") or []
api_by_name = {row.get("name"): row for row in entries}
require(set(api_by_name) == {"JANUS.SEARCH GitHub Ingress", "JANUS.PR_REVIEW GitHub Ingress"}, "APIS_JSON_LIVE_INGRESS_SET_DRIFT")
for entry in api_by_name.values():
    require(
        str(entry.get("baseURL", "")).startswith("https://api.github.com/repos/Hawkar-usls/JANUS-MACHINE-MARKET"),
        "APIS_JSON_BASEURL_DRIFT",
    )
pr_api = api_by_name["JANUS.PR_REVIEW GitHub Ingress"]
require(any(x.get("type") == "OpenAPI" and "PR_REVIEW_GITHUB_INGRESS.openapi.json" in str(x.get("url", "")) for x in (pr_api.get("properties") or [])), "PR_REVIEW_OPENAPI_PROPERTY_MISSING")

require(openapi.get("openapi") == "3.1.0", "INGRESS_OPENAPI_VERSION_DRIFT")
paths = openapi.get("paths") or {}
issue_path = "/repos/Hawkar-usls/JANUS-MACHINE-MARKET/issues"
require(issue_path in paths, "INGRESS_OPENAPI_CREATE_ISSUE_MISSING")
post = (paths[issue_path] or {}).get("post") or {}
require(post.get("operationId") == "createJanusFirstFreeSearchOrder", "INGRESS_OPENAPI_OPERATION_DRIFT")
require((openapi.get("servers") or [{}])[0].get("url") == "https://api.github.com", "INGRESS_OPENAPI_SERVER_DRIFT")
require(pr_openapi.get("openapi") == "3.1.0", "PR_REVIEW_OPENAPI_VERSION_DRIFT")
pr_paths = pr_openapi.get("paths") or {}
require(issue_path in pr_paths, "PR_REVIEW_OPENAPI_CREATE_ISSUE_MISSING")
pr_post = (pr_paths[issue_path] or {}).get("post") or {}
require(pr_post.get("operationId") == "createJanusFirstFreePRReview", "PR_REVIEW_OPENAPI_OPERATION_DRIFT")
require((pr_openapi.get("servers") or [{}])[0].get("url") == "https://api.github.com", "PR_REVIEW_OPENAPI_SERVER_DRIFT")

fast = acq.get("fastest_live_path") or {}
require(fast.get("sku") == "JANUS.SEARCH", "ACQUISITION_SKU_DRIFT")
require(fast.get("price") == 0, "ACQUISITION_FIRST_PRICE_DRIFT")
require(fast.get("telegram_required") is False, "ACQUISITION_FALSE_TELEGRAM_DEPENDENCY")
require(
    fast.get("endpoint") == "https://api.github.com/repos/Hawkar-usls/JANUS-MACHINE-MARKET/issues",
    "ACQUISITION_ENDPOINT_DRIFT",
)

channels = {x.get("id"): x for x in (acq.get("channels") or [])}
require((channels.get("GITHUB_ISSUES_API") or {}).get("status") == "LIVE", "GITHUB_AGENT_INGRESS_NOT_LIVE")
for blocked in ["A2A_AGENT_CARD", "OFFICIAL_MCP_REGISTRY", "X402_BAZAAR", "OPENAPI"]:
    require(str((channels.get(blocked) or {}).get("status", "")).startswith("BLOCKED"), f"PREMATURE_CHANNEL_PROMOTION:{blocked}")

require((pointer.get("fastest_live_order") or {}).get("telegram_required") is False, "POINTER_TELEGRAM_DRIFT")
public_live = set((agent.get("task_execution") or {}).get("public_live_skus") or [])
require(public_live == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "PUBLIC_LIVE_SKU_DRIFT")
offers = {x.get("sku"): x for x in (agent.get("public_first_free_offers") or [])}
require(set(offers) == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "PUBLIC_FIRST_FREE_OFFERS_DRIFT")
require(offers["JANUS.PR_REVIEW"].get("public_repositories_only") is True, "PR_REVIEW_PUBLIC_ONLY_DRIFT")
ingress_live = ingress.get("live_services") or {}
require("JANUS.SEARCH" in ingress_live and "JANUS.PR_REVIEW" in ingress_live, "MACHINE_INGRESS_PUBLIC_SERVICE_SET_DRIFT")
require(str((ingress_live.get("JANUS.SEARCH") or {}).get("status", "")).startswith("LIVE_FIRST_SEARCH_FREE"), "MACHINE_INGRESS_SEARCH_STATUS_DRIFT")
require(str((ingress_live.get("JANUS.PR_REVIEW") or {}).get("status", "")).startswith("LIVE_FIRST_REVIEW_FREE"), "MACHINE_INGRESS_PR_REVIEW_STATUS_DRIFT")
beta_services = public_beta.get("public_services") or {}
require(set(beta_services) == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "PUBLIC_SERVICE_BETA_SET_DRIFT")
require((beta_services["JANUS.PR_REVIEW"] or {}).get("target_repository_code_executed") is False, "PR_REVIEW_TARGET_CODE_EXECUTION_DRIFT")
pointer_offers = {x.get("sku"): x for x in (pointer.get("first_free_offers") or [])}
require(set(pointer_offers) == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "WELL_KNOWN_FIRST_FREE_OFFERS_DRIFT")
live_paths = {x.get("sku"): x for x in (acq.get("live_paths") or [])}
require(set(live_paths) == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "ACQUISITION_LIVE_PATH_SET_DRIFT")
require(live_paths["JANUS.PR_REVIEW"].get("target_repository_code_executed") is False, "ACQUISITION_PR_REVIEW_EXECUTION_DRIFT")
commercial_services = {x.get("sku"): x for x in (commercial.get("public_zero_price_services") or [])}
require(set(commercial_services) == {"JANUS.SEARCH", "JANUS.PR_REVIEW"}, "COMMERCIAL_PUBLIC_SERVICE_SET_DRIFT")
require(commercial_services["JANUS.PR_REVIEW"].get("target_repository_code_executed") is False, "COMMERCIAL_PR_REVIEW_EXECUTION_DRIFT")
for token in ("JANUS.SEARCH", "JANUS.PR_REVIEW", "Two live first-free entrypoints"):
    require(token in readme_text, f"README_PUBLIC_SERVICE_DRIFT:{token}")
for token in ("JANUS.SEARCH", "JANUS.PR_REVIEW", "FIRST FREE OFFERS"):
    require(token in llms_text, f"LLMS_PUBLIC_SERVICE_DRIFT:{token}")
require((ROOT / ".github/workflows/pr-review-public-beta.yml").is_file(), "PR_REVIEW_PUBLIC_WORKFLOW_MISSING")
require((ROOT / ".github/ISSUE_TEMPLATE/janus-pr-review-free-beta.md").is_file(), "PR_REVIEW_PUBLIC_TEMPLATE_MISSING")
require(commerce.get("money_enabled") is False, "ACQUISITION_MUST_NOT_ENABLE_MONEY")
require(witness.get("foreign_agent_witness") is False, "ACQUISITION_METADATA_MUST_NOT_SELF_PROMOTE_WITNESS")

for forbidden in [".well-known/agent-card.json", "server.json", "openapi.json"]:
    require(not (ROOT / forbidden).exists(), f"PREMATURE_PROTOCOL_DESCRIPTOR:{forbidden}")

print("JANUS_AGENT_ACQUISITION_INTEGRITY_PASS")
print("PUBLIC_LIVE_SKUS=JANUS.SEARCH,JANUS.PR_REVIEW")
print("JANUS_PR_REVIEW_PUBLIC_ROUTE=TRUE")
print("TELEGRAM_REQUIRED=FALSE")
print("MONEY_ENABLED=FALSE")
print("A2A_RUNTIME_PROMOTED=FALSE")
print("MCP_RUNTIME_PROMOTED=FALSE")
print("JANUS_SEARCH_AGENT_SKILL=VALID")
print("JANUS_PR_REVIEW_AGENT_SKILL=VALID")
