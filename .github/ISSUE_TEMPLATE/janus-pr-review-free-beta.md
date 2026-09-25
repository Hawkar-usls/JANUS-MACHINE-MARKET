---
name: JANUS PR Guard — first review free
about: Request one bounded structural review of a public GitHub pull request
title: "[JANUS PR REVIEW] First-free public request"
labels: ""
assignees: ""
---

Your first new `JANUS.PR_REVIEW` request as an external GitHub principal is free during the bounded beta.

Requirements:

- the target repository and pull request must be public;
- freeze the exact current PR head SHA before submitting;
- one PR review per issue;
- target repository code is never executed;
- this is structural/policy-risk review, not merge approval or security certification.

Replace the example values below.

<!-- JANUS_PR_REVIEW_PUBLIC_JSON
{"schema":"janus.pr_review.public_request.v1","repository":"OWNER/REPOSITORY","pull_number":123,"expected_head_sha":"0123456789abcdef0123456789abcdef01234567"}
JANUS_PR_REVIEW_PUBLIC_JSON -->
