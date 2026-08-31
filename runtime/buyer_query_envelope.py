#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

GRANT_SCHEMA = "janus.machine_market.purchase_grant.v1"
QUERY_SCHEMA = "janus.machine_market.buyer_query.v1"


class BuyerQueryError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise BuyerQueryError(code)


def build_query(
    grant: dict[str, Any],
    *,
    buyer_actor_id: str,
    conversation_id: str,
    turn_index: int,
    message_text: str,
    conversation_history: list[dict[str, str]] | None = None,
    requested_output: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    require(grant.get("schema") == GRANT_SCHEMA, "PURCHASE_GRANT_SCHEMA_INVALID")
    require(grant.get("status") == "PURCHASE_ELIGIBLE", "PURCHASE_GRANT_NOT_ELIGIBLE")
    require(grant.get("execution_authority_granted") is False, "PURCHASE_GRANT_MUST_NOT_GRANT_EXECUTION_AUTHORITY")

    purchase_id = str(grant.get("purchase_id") or "").strip()
    sku = str(grant.get("sku") or "").strip()
    require(bool(purchase_id and sku), "PURCHASE_GRANT_IDENTITY_REQUIRED")

    entitlement = grant.get("buyer_query_entitlement")
    require(isinstance(entitlement, dict), "BUYER_QUERY_ENTITLEMENT_REQUIRED")
    require(entitlement.get("enabled") is True, "BUYER_QUERY_ENTITLEMENT_DISABLED")
    require(entitlement.get("read_only_conversation") is True, "BUYER_QUERY_MUST_BE_READ_ONLY")
    require(entitlement.get("external_effect_authorized") is False, "BUYER_QUERY_EXTERNAL_EFFECT_FORBIDDEN")

    actor = str(buyer_actor_id).strip()
    expected_actor = str(entitlement.get("buyer_actor_id") or "").strip()
    require(actor and actor == expected_actor, "BUYER_ACTOR_NOT_ENTITLED")

    conversation = str(conversation_id).strip()
    require(bool(conversation), "CONVERSATION_ID_REQUIRED")
    require(isinstance(turn_index, int) and not isinstance(turn_index, bool) and turn_index >= 0, "TURN_INDEX_INVALID")
    max_turns = int(entitlement.get("max_turns", 0))
    require(turn_index < max_turns, "QUERY_TURN_BUDGET_EXHAUSTED")

    text = str(message_text).strip()
    require(bool(text), "BUYER_QUERY_TEXT_REQUIRED")
    max_message_bytes = int(entitlement.get("max_message_utf8_bytes", 0))
    require(0 < len(text.encode("utf-8")) <= max_message_bytes, "BUYER_QUERY_TEXT_SIZE_EXCEEDED")

    history = list(conversation_history or [])
    history_limit = int(entitlement.get("conversation_history_turns", 0))
    require(len(history) <= history_limit, "BUYER_QUERY_HISTORY_LIMIT_EXCEEDED")
    for item in history:
        require(isinstance(item, dict), "BUYER_QUERY_HISTORY_ITEM_INVALID")
        require(item.get("role") in {"buyer", "janus"}, "BUYER_QUERY_HISTORY_ROLE_INVALID")
        require(isinstance(item.get("content"), str), "BUYER_QUERY_HISTORY_CONTENT_INVALID")

    nonce = str(entitlement.get("entitlement_nonce") or "").strip()
    require(len(nonce) >= 16, "BUYER_QUERY_ENTITLEMENT_NONCE_INVALID")

    purchase_grant_hash = digest(grant)
    message_hash = digest(text)
    query_id = "bq-" + digest({
        "purchase_id": purchase_id,
        "conversation_id": conversation,
        "turn_index": turn_index,
        "message_hash": message_hash,
        "entitlement_nonce": nonce,
    })

    body: dict[str, Any] = {
        "schema": QUERY_SCHEMA,
        "purchase_id": purchase_id,
        "purchase_grant_hash": purchase_grant_hash,
        "sku": sku,
        "buyer_actor_id": actor,
        "conversation_id": conversation,
        "turn_index": turn_index,
        "entitlement_nonce": nonce,
        "message_text": text,
        "message_hash": message_hash,
        "query_id": query_id,
        "conversation_history": history,
        "requested_output": requested_output,
        "created_at": created_at,
    }
    body["query_hash"] = digest(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a bounded JANUS Machine Market post-purchase buyer query envelope")
    parser.add_argument("--grant", required=True)
    parser.add_argument("--buyer-actor", required=True)
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--turn-index", required=True, type=int)
    parser.add_argument("--message", required=True)
    parser.add_argument("--history")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    grant = json.loads(Path(args.grant).read_text(encoding="utf-8"))
    history = json.loads(Path(args.history).read_text(encoding="utf-8")) if args.history else []
    query = build_query(
        grant,
        buyer_actor_id=args.buyer_actor,
        conversation_id=args.conversation_id,
        turn_index=args.turn_index,
        message_text=args.message,
        conversation_history=history,
    )
    text = json.dumps(query, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
