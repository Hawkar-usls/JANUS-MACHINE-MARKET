---
name: janus-pr-review
description: Review a public GitHub pull request with JANUS PR Guard using an exact frozen head SHA and receive a structural/policy-risk result plus durable receipt.
---

# JANUS.PR_REVIEW

Use this skill when an agent needs an independent bounded review of a public GitHub pull request before merge or handoff.

## Live public beta

The first new PR review for each external GitHub principal is free.

Requirements:

- target repository and pull request must be public;
- freeze the exact current 40-hex PR head SHA;
- maximum 300 changed files;
- target repository code is never executed;
- maximum 10 accepted public PR reviews per UTC day.

Create an issue in `Hawkar-usls/JANUS-MACHINE-MARKET`.

Title:

`[JANUS PR REVIEW] First-free public request`

Body:

```text
<!-- JANUS_PR_REVIEW_PUBLIC_JSON
{"schema":"janus.pr_review.public_request.v1","repository":"OWNER/REPOSITORY","pull_number":123,"expected_head_sha":"40_HEX_PR_HEAD_SHA"}
JANUS_PR_REVIEW_PUBLIC_JSON -->
```

## What JANUS checks

The current deterministic guard checks:

- exact base/head SHA binding;
- snapshot completeness and patch coverage;
- GitHub workflow changes;
- addition of `pull_request_target`;
- added workflow write permissions;
- added workflow secret references;
- remote script piping to shell;
- third-party Actions not pinned to a full commit SHA;
- dependency manifest changes without a lockfile change;
- source changes without test-file changes;
- test-file removals;
- governance-file changes or removals;
- changeset breadth.

## Result

The result returns to the same issue and includes:

- `verdict`;
- structural score;
- severity counts;
- finding codes;
- exact PR head SHA;
- result SHA-256;
- durable receipt ID/hash;
- Market state commit.

## Important boundary

This is a bounded structural/diff risk audit.

It is not:

- merge approval;
- a proof of semantic correctness;
- an exploitability finding;
- a security certification;
- permission to execute or modify the target repository.

A PASS means the declared deterministic checks did not find a configured structural risk signal in the captured snapshot. It does not mean the pull request is correct or safe in every respect.
