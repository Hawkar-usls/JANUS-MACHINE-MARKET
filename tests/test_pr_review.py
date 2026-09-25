from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pr_review", ROOT / "runtime/pr_review.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

def load(name: str):
    return json.loads((ROOT / "tests/fixtures" / name).read_text(encoding="utf-8"))

def test_pass_fixture():
    snap = load("pr_review_pass.json")
    result = mod.audit_snapshot(snap)
    assert result["verdict"] == "PASS"
    assert result["score_0_100"] == 100
    assert result["severity_counts"] == {"high": 0, "medium": 0, "low": 0}
    assert mod.verify_result(snap, result)

def test_fail_fixture():
    snap = load("pr_review_fail.json")
    result = mod.audit_snapshot(snap)
    assert result["verdict"] == "FAIL"
    codes = {x["code"] for x in result["findings"]}
    required = {
        "GITHUB_WORKFLOW_CHANGED",
        "PULL_REQUEST_TARGET_ADDED",
        "WORKFLOW_WRITE_PERMISSION_ADDED",
        "WORKFLOW_SECRET_REFERENCE_ADDED",
        "REMOTE_SCRIPT_PIPE_TO_SHELL_ADDED",
        "ACTION_NOT_PINNED_TO_FULL_SHA",
        "DEPENDENCY_MANIFEST_WITHOUT_LOCKFILE_CHANGE",
        "SOURCE_CHANGED_WITHOUT_TEST_FILE_CHANGE",
    }
    assert required <= codes
    assert result["severity_counts"]["high"] >= 3
    assert mod.verify_result(snap, result)

def test_incomplete_snapshot_fails_closed():
    snap = load("pr_review_pass.json")
    snap["snapshot_complete"] = False
    snap["changed_files_reported"] = 3
    result = mod.audit_snapshot(snap)
    assert result["verdict"] == "FAIL"
    assert any(x["code"] == "PR_SNAPSHOT_INCOMPLETE" for x in result["findings"])

if __name__ == "__main__":
    test_pass_fixture()
    test_fail_fixture()
    test_incomplete_snapshot_fails_closed()
    print("JANUS_PR_REVIEW_TESTS=PASS")
