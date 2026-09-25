#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA = "janus.pr_review.snapshot.v1"
RESULT_SCHEMA = "janus.pr_review.result.v1"
SKU = "JANUS.PR_REVIEW"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
LOCKFILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock",
}
MANIFESTS = {
    "package.json", "requirements.txt", "pyproject.toml", "Pipfile",
    "Cargo.toml", "go.mod", "Gemfile", "composer.json",
}
SOURCE_EXTS = {".py",".js",".mjs",".cjs",".ts",".tsx",".jsx",".go",".rs",".java",".kt",".kts",".rb",".php",".cs",".cpp",".cc",".c",".h",".hpp",".swift"}
TEST_HINTS = ("/test/","/tests/","test_","_test.","spec.","/spec/")
WORKFLOW_PREFIX = ".github/workflows/"
SENSITIVE_GOVERNANCE = {".github/CODEOWNERS","CODEOWNERS","SECURITY.md",".github/dependabot.yml"}

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)

def _added_lines(patch: str) -> list[str]:
    return [line[1:] for line in str(patch or "").splitlines() if line.startswith("+") and not line.startswith("+++")]

def _deleted_lines(patch: str) -> list[str]:
    return [line[1:] for line in str(patch or "").splitlines() if line.startswith("-") and not line.startswith("---")]

def _is_test(path: str) -> bool:
    p = "/" + path.lower()
    return any(h in p for h in TEST_HINTS)

def _is_source(path: str) -> bool:
    return Path(path).suffix.lower() in SOURCE_EXTS and not _is_test(path)

def _finding(code: str, severity: str, path: str | None = None, **detail: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "severity": severity}
    if path:
        row["path"] = path
    row.update(detail)
    return row

def audit_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(snapshot, dict), "PR_REVIEW_SNAPSHOT_OBJECT_REQUIRED")
    require(snapshot.get("schema") == SNAPSHOT_SCHEMA, "PR_REVIEW_SNAPSHOT_SCHEMA_INVALID")
    repository = str(snapshot.get("repository") or "").strip()
    require(SAFE_REPO.fullmatch(repository) is not None, "PR_REVIEW_REPOSITORY_INVALID")
    pull_number = snapshot.get("pull_number")
    require(isinstance(pull_number, int) and not isinstance(pull_number, bool) and pull_number > 0, "PR_REVIEW_PULL_NUMBER_INVALID")
    base_sha = str(snapshot.get("base_sha") or "")
    head_sha = str(snapshot.get("head_sha") or "")
    require(HEX40.fullmatch(base_sha) is not None and HEX40.fullmatch(head_sha) is not None, "PR_REVIEW_SHA_BINDING_INVALID")
    require(base_sha != head_sha, "PR_REVIEW_BASE_EQUALS_HEAD")

    files = snapshot.get("files")
    require(isinstance(files, list), "PR_REVIEW_FILES_REQUIRED")
    require(len(files) <= 300, "PR_REVIEW_FILE_CAP_EXCEEDED")
    snapshot_complete = bool(snapshot.get("snapshot_complete", False))
    changed_files_reported = int(snapshot.get("changed_files_reported") or len(files))
    require(changed_files_reported >= len(files), "PR_REVIEW_CHANGED_FILES_COUNT_INVALID")

    findings: list[dict[str, Any]] = []
    metrics = {
        "files_captured": len(files),
        "changed_files_reported": changed_files_reported,
        "additions": int(snapshot.get("additions") or 0),
        "deletions": int(snapshot.get("deletions") or 0),
        "workflow_files_changed": 0,
        "dependency_manifests_changed": 0,
        "lockfiles_changed": 0,
        "test_files_changed": 0,
        "source_files_changed": 0,
        "patches_missing": 0,
        "files_removed": 0,
    }

    manifests_changed: set[str] = set()
    lockfiles_changed: set[str] = set()
    source_changed = False
    tests_changed = False

    if not snapshot_complete:
        findings.append(_finding("PR_SNAPSHOT_INCOMPLETE", "high", captured=len(files), reported=changed_files_reported))
    if changed_files_reported > 100:
        findings.append(_finding("LARGE_CHANGESET", "medium", reported_files=changed_files_reported))
    elif changed_files_reported > 40:
        findings.append(_finding("BROAD_CHANGESET", "low", reported_files=changed_files_reported))

    for idx, row in enumerate(files):
        require(isinstance(row, dict), f"PR_REVIEW_FILE_OBJECT_REQUIRED:{idx}")
        path = str(row.get("filename") or "").strip()
        require(bool(path) and not path.startswith("/") and ".." not in Path(path).parts, f"PR_REVIEW_FILE_PATH_INVALID:{idx}")
        status = str(row.get("status") or "").strip()
        patch = row.get("patch")
        patch_missing = not isinstance(patch, str)
        if patch_missing:
            metrics["patches_missing"] += 1
            findings.append(_finding("PATCH_UNAVAILABLE", "low", path, status=status))
            patch = ""
        added = _added_lines(patch)
        deleted = _deleted_lines(patch)
        lower = path.lower()
        base = Path(path).name

        if status == "removed":
            metrics["files_removed"] += 1
        if _is_source(path):
            source_changed = True
            metrics["source_files_changed"] += 1
        if _is_test(path):
            tests_changed = True
            metrics["test_files_changed"] += 1
            if status == "removed":
                findings.append(_finding("TEST_FILE_REMOVED", "high", path))
        if base in MANIFESTS:
            manifests_changed.add(base)
            metrics["dependency_manifests_changed"] += 1
        if base in LOCKFILES:
            lockfiles_changed.add(base)
            metrics["lockfiles_changed"] += 1

        if path in SENSITIVE_GOVERNANCE or lower.endswith("/codeowners"):
            findings.append(_finding("GOVERNANCE_FILE_CHANGED", "medium", path, status=status))

        if path.startswith(WORKFLOW_PREFIX) and path.endswith((".yml",".yaml")):
            metrics["workflow_files_changed"] += 1
            findings.append(_finding("GITHUB_WORKFLOW_CHANGED", "medium", path, status=status))
            text = "\n".join(added)
            if re.search(r"(?m)^\s*pull_request_target\s*:", text):
                findings.append(_finding("PULL_REQUEST_TARGET_ADDED", "high", path))
            if re.search(r"(?mi)^\s*(contents|actions|checks|deployments|issues|packages|pages|pull-requests|repository-projects|security-events|statuses|id-token)\s*:\s*write\s*$", text):
                findings.append(_finding("WORKFLOW_WRITE_PERMISSION_ADDED", "high", path))
            if re.search(r"\$\{\{\s*secrets\.", text):
                findings.append(_finding("WORKFLOW_SECRET_REFERENCE_ADDED", "medium", path))
            if re.search(r"(?i)(curl|wget)[^\n|]{0,240}\|\s*(ba)?sh\b", text):
                findings.append(_finding("REMOTE_SCRIPT_PIPE_TO_SHELL_ADDED", "high", path))
            for line in added:
                m = re.search(r"\buses\s*:\s*([^\s#]+)@([^\s#]+)", line)
                if not m:
                    continue
                target, ref = m.group(1), m.group(2)
                if target.startswith("./"):
                    continue
                if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
                    findings.append(_finding("ACTION_NOT_PINNED_TO_FULL_SHA", "low", path, action=target))

        ext = Path(path).suffix.lower()
        if ext in {".sh",".bash",".zsh",".py",".js",".mjs",".ts",".ps1"} or path.startswith(WORKFLOW_PREFIX):
            text = "\n".join(added)
            if re.search(r"(?m)(^|[;&|]\s*)eval\s+[^\n]+", text):
                findings.append(_finding("DYNAMIC_EVAL_ADDED", "medium", path))
            if re.search(r"(?i)(curl|wget)[^\n|]{0,240}\|\s*(ba)?sh\b", text) and not path.startswith(WORKFLOW_PREFIX):
                findings.append(_finding("REMOTE_SCRIPT_PIPE_TO_SHELL_ADDED", "high", path))

        if deleted and path in {"SECURITY.md",".github/CODEOWNERS","CODEOWNERS"} and status == "removed":
            findings.append(_finding("GOVERNANCE_FILE_REMOVED", "high", path))

    if manifests_changed and not lockfiles_changed:
        findings.append(_finding("DEPENDENCY_MANIFEST_WITHOUT_LOCKFILE_CHANGE", "medium", manifests=sorted(manifests_changed)))
    if source_changed and not tests_changed:
        findings.append(_finding("SOURCE_CHANGED_WITHOUT_TEST_FILE_CHANGE", "medium"))
    if metrics["patches_missing"] and metrics["patches_missing"] == len(files):
        findings.append(_finding("NO_TEXT_PATCH_COVERAGE", "high"))

    # De-duplicate exact findings while preserving first occurrence.
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in findings:
        key = canonical(row)
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    findings = deduped

    severity_counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("high","medium","low")}
    if severity_counts["high"]:
        verdict = "FAIL"
    elif findings:
        verdict = "WARN"
    else:
        verdict = "PASS"

    score = max(0, 100 - severity_counts["high"]*25 - severity_counts["medium"]*8 - severity_counts["low"]*2)
    snapshot_sha = digest(snapshot)
    core = {
        "schema": RESULT_SCHEMA,
        "sku": SKU,
        "repository": repository,
        "pull_number": pull_number,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "verdict": verdict,
        "score_0_100": score,
        "snapshot_complete": snapshot_complete,
        "metrics": metrics,
        "severity_counts": severity_counts,
        "findings": findings,
        "snapshot_sha256": snapshot_sha,
        "truth_boundary": [
            "STRUCTURAL_PR_REVIEW != FULL_SEMANTIC_CORRECTNESS_PROOF",
            "PASS != MERGE_APPROVAL",
            "FAIL != EXPLOITABILITY_PROOF",
            "PATCH_UNAVAILABLE_REDUCES_COVERAGE",
            "REVIEW_DOES_NOT_EXECUTE_TARGET_REPOSITORY_CODE",
        ],
    }
    core["result_sha256"] = digest(core)
    return core

def verify_result(snapshot: dict[str, Any], result: dict[str, Any]) -> bool:
    try:
        if result.get("schema") != RESULT_SCHEMA or result.get("sku") != SKU:
            return False
        if result.get("snapshot_sha256") != digest(snapshot):
            return False
        if result.get("repository") != snapshot.get("repository") or result.get("pull_number") != snapshot.get("pull_number"):
            return False
        if result.get("base_sha") != snapshot.get("base_sha") or result.get("head_sha") != snapshot.get("head_sha"):
            return False
        value = dict(result)
        claimed = str(value.pop("result_sha256", ""))
        return len(claimed) == 64 and digest(value) == claimed
    except Exception:
        return False

def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS deterministic structural PR Guard")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    result = audit_snapshot(snapshot)
    require(verify_result(snapshot, result), "PR_REVIEW_RESULT_SELF_VERIFY_FAILED")
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("JANUS_PR_REVIEW=PASS")
    print("VERDICT=" + result["verdict"])
    print("SCORE=" + str(result["score_0_100"]))
    print("SNAPSHOT_SHA256=" + result["snapshot_sha256"])
    print("RESULT_SHA256=" + result["result_sha256"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
