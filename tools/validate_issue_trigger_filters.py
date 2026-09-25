#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RULES = {
    ".github/workflows/pr-review-public-beta.yml": {
        "prefix": "[JANUS PR REVIEW]",
        "actor": "github.event.issue.user.login != github.repository_owner",
    },
    ".github/workflows/pr-review-integrity.yml": {
        "prefix": "[JANUS PR REVIEW SHADOW]",
        "actor": "github.event.issue.user.login == github.repository_owner",
    },
    ".github/workflows/r1-public-search-beta-outbox.yml": {
        "prefix": "[JANUS R1B BUYER QUERY SHADOW]",
        "actor": "github.event.issue.user.login != github.repository_owner",
    },
    ".github/workflows/r1b-buyer-query-shadow-outbox.yml": {
        "prefix": "[JANUS R1B BUYER QUERY SHADOW]",
        "actor": "github.event.issue.user.login == github.repository_owner",
    },
    ".github/workflows/r1e-foreign-machine-claim-freeze.yml": {
        "prefix": "[JANUS R1B BUYER QUERY SHADOW]",
        "actor": "github.event.issue.user.login != github.repository_owner",
    },
    ".github/workflows/r2-repo-audit-shadow-outbox.yml": {
        "prefix": "[JANUS REPO AUDIT SHADOW]",
        "actor": "github.event.issue.user.login == github.repository_owner",
    },
    ".github/workflows/r3-dataset-scout-shadow-outbox.yml": {
        "prefix": "[JANUS DATASET SCOUT SHADOW]",
        "actor": "github.event.issue.user.login == github.repository_owner",
    },
    ".github/workflows/paid-search-checkout.yml": {
        "prefix": "[JANUS PAID SEARCH]",
        "actor": "github.event.issue.user.login != github.repository_owner",
        "comment_marker": "JANUS_PAYMENT_PROOF_JSON",
    },
    ".github/workflows/a2a-live-registry-gate.yml": {
        "prefix": "[JANUS A2A LIVE GATE]",
        "actor": "github.event.issue.user.login == github.repository_owner",
    },
}

def contract_header(text: str) -> str:
    start = text.find("\njobs:\n")
    if start < 0:
        raise AssertionError("JOBS_BLOCK_MISSING")
    start = text.find("\n  contract:\n", start)
    if start < 0:
        raise AssertionError("CONTRACT_JOB_MISSING")
    end = text.find("\n    runs-on:", start)
    if end < 0:
        raise AssertionError("CONTRACT_RUNS_ON_MISSING")
    return text[start:end]

for rel, rule in RULES.items():
    path = ROOT / rel
    if not path.is_file():
        raise SystemExit(f"ISSUE_TRIGGER_WORKFLOW_MISSING:{rel}")
    text = path.read_text(encoding="utf-8")
    if "\n  issues:\n" not in text and "\n  issue_comment:\n" not in text:
        raise SystemExit(f"ISSUE_TRIGGER_EVENT_MISSING:{rel}")
    try:
        head = contract_header(text)
    except AssertionError as exc:
        raise SystemExit(f"{exc}:{rel}") from exc
    prefix = rule["prefix"]
    if "if: >-" not in head:
        raise SystemExit(f"UNGUARDED_CONTRACT_JOB:{rel}")
    if prefix not in head:
        raise SystemExit(f"CONTRACT_PREFIX_FILTER_MISSING:{rel}")
    if rule["actor"] not in head:
        raise SystemExit(f"CONTRACT_ACTOR_FILTER_MISSING:{rel}")
    if rule.get("comment_marker") and rule["comment_marker"] not in head:
        raise SystemExit(f"CONTRACT_COMMENT_MARKER_FILTER_MISSING:{rel}")

print("JANUS_ISSUE_TRIGGER_INTEGRITY_PASS")
print("FILTERED_WORKFLOWS=" + str(len(RULES)))
print("UNRELATED_ISSUES_RUN_SERVICE_CONTRACTS=FALSE")
