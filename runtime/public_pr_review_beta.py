#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

REQUEST_SCHEMA = "janus.pr_review.public_request.v1"
PUBLIC_ORIGIN = "FOREIGN_PUBLIC_ZERO_PRICE_BETA"
OWNER_LOGIN = "Hawkar-usls"
FIRST_FREE_PER_ACTOR = 1
GLOBAL_DAILY_LIMIT = 10

def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)

def utc_day(value: str) -> str:
    text=str(value or "").strip()
    require(bool(text),"PR_REVIEW_PUBLIC_CREATED_AT_REQUIRED")
    if text.endswith("Z"):
        text=text[:-1]+"+00:00"
    dt=datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date().isoformat()

def normalize_public_request(issue: dict[str,Any], request: dict[str,Any], *, owner_login: str=OWNER_LOGIN) -> dict[str,Any]:
    login=str((issue.get("user") or {}).get("login") or "").strip()
    require(bool(login),"PR_REVIEW_PUBLIC_GITHUB_LOGIN_REQUIRED")
    require(login.lower()!=owner_login.lower(),"PR_REVIEW_PUBLIC_OWNER_MUST_USE_OWNER_SHADOW")
    require(request.get("schema")==REQUEST_SCHEMA,"PR_REVIEW_PUBLIC_REQUEST_SCHEMA_INVALID")
    repository=str(request.get("repository") or "").strip()
    parts=repository.split("/")
    require(len(parts)==2 and all(parts),"PR_REVIEW_PUBLIC_REPOSITORY_INVALID")
    pull_number=request.get("pull_number")
    require(isinstance(pull_number,int) and not isinstance(pull_number,bool) and pull_number>0,"PR_REVIEW_PUBLIC_PULL_NUMBER_INVALID")
    head=str(request.get("expected_head_sha") or "").strip()
    require(len(head)==40 and all(c in "0123456789abcdef" for c in head),"PR_REVIEW_PUBLIC_EXPECTED_HEAD_SHA_INVALID")
    issue_id=int(issue.get("id") or 0)
    issue_number=int(issue.get("number") or 0)
    created_at=str(issue.get("created_at") or "").strip()
    require(issue_id>0 and issue_number>0,"PR_REVIEW_PUBLIC_ISSUE_IDENTITY_INVALID")
    utc_day(created_at)
    return {
        "schema":REQUEST_SCHEMA,
        "request_origin":PUBLIC_ORIGIN,
        "buyer_actor_id":f"github:{login}",
        "source_issue_id":issue_id,
        "source_issue_number":issue_number,
        "created_at":created_at,
        "repository":repository,
        "pull_number":pull_number,
        "expected_head_sha":head,
    }

def evaluate_admission(request: dict[str,Any], receipts: Iterable[dict[str,Any]]) -> dict[str,Any]:
    actor=request["buyer_actor_id"]
    issue_id=request["source_issue_id"]
    day=utc_day(request["created_at"])
    actor_prior=0
    global_today=0
    for receipt in receipts:
        if receipt.get("request_origin")!=PUBLIC_ORIGIN:
            continue
        if int(receipt.get("source_issue_id") or 0)==issue_id:
            same=(receipt.get("buyer_actor_id")==actor and receipt.get("repository")==request.get("repository") and receipt.get("pull_number")==request.get("pull_number") and receipt.get("expected_head_sha")==request.get("expected_head_sha"))
            return {"admitted":False,"reason":"EXACT_RETRY_ALREADY_DELIVERED" if same else "ISSUE_ALREADY_BOUND_TO_DIFFERENT_PR","existing_receipt_id":receipt.get("receipt_id") if same else None}
        if receipt.get("buyer_actor_id")==actor:
            actor_prior+=1
        try:
            if utc_day(str(receipt.get("requested_at") or ""))==day:
                global_today+=1
        except Exception:
            pass
    if actor_prior>=FIRST_FREE_PER_ACTOR:
        return {"admitted":False,"reason":"FIRST_FREE_PR_REVIEW_ALREADY_USED","limit":FIRST_FREE_PER_ACTOR}
    if global_today>=GLOBAL_DAILY_LIMIT:
        return {"admitted":False,"reason":"GLOBAL_DAILY_LIMIT_REACHED","limit":GLOBAL_DAILY_LIMIT}
    return {"admitted":True,"reason":"PUBLIC_BETA_ADMITTED"}
