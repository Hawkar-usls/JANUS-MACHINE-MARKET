#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REQUEST_SCHEMA = "janus.machine_market.buyer_query_shadow_request.v1"
PUBLIC_ORIGIN = "FOREIGN_PUBLIC_ZERO_PRICE_BETA"
OWNER_LOGIN = "Hawkar-usls"
SKU = "JANUS.SEARCH"
MAX_MESSAGE_UTF8_BYTES = 4000
MAX_ANSWER_UTF8_BYTES = 6000
MAX_TURNS = 1
HISTORY_TURNS = 0
PER_ACTOR_DAILY_LIMIT = 3
GLOBAL_DAILY_LIMIT = 20


class PublicSearchBetaError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PublicSearchBetaError(code)


def _utc_day(value: str) -> str:
    text = str(value or "").strip()
    require(bool(text), "PUBLIC_BETA_CREATED_AT_REQUIRED")
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date().isoformat()
    except Exception as exc:  # noqa: BLE001
        raise PublicSearchBetaError("PUBLIC_BETA_CREATED_AT_INVALID") from exc


def normalize_external_issue_request(issue: dict[str, Any], request: dict[str, Any], *, owner_login: str = OWNER_LOGIN) -> dict[str, Any]:
    require(isinstance(issue, dict), "PUBLIC_BETA_ISSUE_REQUIRED")
    user = issue.get("user") or {}
    login = str(user.get("login") or "").strip()
    require(bool(login), "PUBLIC_BETA_GITHUB_LOGIN_REQUIRED")
    require(login.lower() != owner_login.lower(), "PUBLIC_BETA_OWNER_MUST_USE_OWNER_SHADOW")
    require(request.get("schema") == REQUEST_SCHEMA, "PUBLIC_BETA_REQUEST_SCHEMA_INVALID")

    message_text = str(request.get("message_text") or "").strip()
    require(bool(message_text), "PUBLIC_BETA_MESSAGE_REQUIRED")
    require(len(message_text.encode("utf-8")) <= MAX_MESSAGE_UTF8_BYTES, "PUBLIC_BETA_MESSAGE_TOO_LARGE")

    issue_id = int(issue.get("id") or 0)
    issue_number = int(issue.get("number") or 0)
    require(issue_id > 0 and issue_number > 0, "PUBLIC_BETA_ISSUE_IDENTITY_INVALID")
    created_at = str(issue.get("created_at") or "").strip()
    _utc_day(created_at)

    return {
        "schema": REQUEST_SCHEMA,
        "request_id": f"github-issue-id:{issue_id}",
        "sku": SKU,
        "buyer_actor_id": f"github:{login}",
        "conversation_id": f"public-market-issue-{issue_id}",
        "turn_index": 0,
        "message_text": message_text,
        "created_at": created_at,
        "max_turns": MAX_TURNS,
        "max_message_utf8_bytes": MAX_MESSAGE_UTF8_BYTES,
        "max_answer_utf8_bytes": MAX_ANSWER_UTF8_BYTES,
        "conversation_history_turns": HISTORY_TURNS,
        "source_issue_number": issue_number,
        "source_issue_id": issue_id,
        "request_origin": PUBLIC_ORIGIN,
    }


def iter_outbox_packets(outbox_root: Path) -> Iterable[dict[str, Any]]:
    root = outbox_root / ".janus/market-home-outbox"
    if not root.exists():
        return []
    values: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.packet.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def evaluate_outbox_admission(packet: dict[str, Any], existing_packets: Iterable[dict[str, Any]]) -> dict[str, Any]:
    if packet.get("request_origin") != PUBLIC_ORIGIN:
        return {"admitted": True, "reason": "NOT_PUBLIC_BETA", "exact_retry": False}

    query = packet.get("buyer_query") or {}
    route = packet.get("return_route") or {}
    actor = str(query.get("buyer_actor_id") or "").strip()
    created_at = str(query.get("created_at") or "").strip()
    issue_id = int(route.get("source_issue_id") or 0)
    qid = str(packet.get("query_id") or "")
    require(actor.startswith("github:"), "PUBLIC_BETA_ACTOR_INVALID")
    require(actor.lower() != f"github:{OWNER_LOGIN}".lower(), "PUBLIC_BETA_OWNER_ACTOR_INVALID")
    require(issue_id > 0 and bool(qid), "PUBLIC_BETA_PACKET_BINDING_INVALID")
    day = _utc_day(created_at)

    actor_count = 0
    global_count = 0
    for prior in existing_packets:
        if prior.get("request_origin") != PUBLIC_ORIGIN:
            continue
        pquery = prior.get("buyer_query") or {}
        proute = prior.get("return_route") or {}
        prior_issue_id = int(proute.get("source_issue_id") or 0)
        prior_qid = str(prior.get("query_id") or "")
        if prior_issue_id == issue_id:
            if prior_qid == qid:
                return {"admitted": True, "reason": "EXACT_RETRY", "exact_retry": True}
            return {"admitted": False, "reason": "ISSUE_ALREADY_BOUND_TO_DIFFERENT_QUERY", "exact_retry": False}
        try:
            prior_day = _utc_day(str(pquery.get("created_at") or ""))
        except PublicSearchBetaError:
            continue
        if prior_day != day:
            continue
        global_count += 1
        if str(pquery.get("buyer_actor_id") or "") == actor:
            actor_count += 1

    if actor_count >= PER_ACTOR_DAILY_LIMIT:
        return {
            "admitted": False,
            "reason": "PER_ACTOR_DAILY_LIMIT_REACHED",
            "exact_retry": False,
            "actor_count": actor_count,
            "limit": PER_ACTOR_DAILY_LIMIT,
        }
    if global_count >= GLOBAL_DAILY_LIMIT:
        return {
            "admitted": False,
            "reason": "GLOBAL_DAILY_LIMIT_REACHED",
            "exact_retry": False,
            "global_count": global_count,
            "limit": GLOBAL_DAILY_LIMIT,
        }
    return {
        "admitted": True,
        "reason": "PUBLIC_BETA_ADMITTED",
        "exact_retry": False,
        "actor_count_before": actor_count,
        "global_count_before": global_count,
    }


def evaluate_outbox_directory(packet: dict[str, Any], outbox_root: Path) -> dict[str, Any]:
    return evaluate_outbox_admission(packet, iter_outbox_packets(outbox_root))


__all__ = [
    "GLOBAL_DAILY_LIMIT",
    "HISTORY_TURNS",
    "MAX_ANSWER_UTF8_BYTES",
    "MAX_MESSAGE_UTF8_BYTES",
    "MAX_TURNS",
    "OWNER_LOGIN",
    "PER_ACTOR_DAILY_LIMIT",
    "PUBLIC_ORIGIN",
    "PublicSearchBetaError",
    "evaluate_outbox_admission",
    "evaluate_outbox_directory",
    "normalize_external_issue_request",
]
