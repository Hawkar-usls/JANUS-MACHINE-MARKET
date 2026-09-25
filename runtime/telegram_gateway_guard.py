from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Iterable, Mapping

MAX_BODY_BYTES = 65536
MAX_TEXT_BYTES = 4000
MAX_CLOCK_SKEW_SECONDS = 300
MAX_HOPS = 1

class TelegramGatewayError(ValueError):
    pass

def require(condition: bool, code: str) -> None:
    if not condition:
        raise TelegramGatewayError(code)

def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256_hex(value: bytes | str) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()

def verify_telegram_webhook_secret(received: str | None, expected: str) -> None:
    require(bool(expected), "TELEGRAM_WEBHOOK_SECRET_NOT_CONFIGURED")
    require(bool(received), "TELEGRAM_WEBHOOK_SECRET_MISSING")
    require(hmac.compare_digest(str(received), str(expected)), "TELEGRAM_WEBHOOK_SECRET_INVALID")

def normalize_telegram_update(update: Mapping[str, Any]) -> dict[str, Any]:
    require(isinstance(update, Mapping), "TELEGRAM_UPDATE_REQUIRED")
    update_id = int(update.get("update_id") or -1)
    require(update_id >= 0, "TELEGRAM_UPDATE_ID_INVALID")
    require("edited_message" not in update, "EDITED_ORDER_MESSAGE_DENIED")
    message = update.get("message")
    require(isinstance(message, Mapping), "TELEGRAM_MESSAGE_REQUIRED")
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    require(str(chat.get("type") or "") == "private", "TELEGRAM_ORDER_PRIVATE_CHAT_REQUIRED")
    user_id = int(sender.get("id") or 0)
    require(user_id > 0, "TELEGRAM_PRINCIPAL_INVALID")
    is_bot = bool(sender.get("is_bot"))
    text = str(message.get("text") or "").strip()
    require(bool(text), "TELEGRAM_TEXT_REQUIRED")
    require(len(text.encode("utf-8")) <= MAX_TEXT_BYTES, "TELEGRAM_TEXT_TOO_LARGE")
    return {
        "platform": "telegram",
        "update_id": update_id,
        "message_id": int(message.get("message_id") or 0),
        "chat_id": int(chat.get("id") or 0),
        "principal_id": f"telegram:{'bot' if is_bot else 'user'}:{user_id}",
        "principal_kind": "BOT" if is_bot else "HUMAN",
        "text": text,
        "idempotency_key": f"telegram-update:{update_id}",
        "hop_count": 0,
    }

def machine_signature(*, key: bytes, key_id: str, timestamp: int, nonce: str, body: bytes, hop_count: int) -> str:
    payload = "\n".join([
        key_id,
        str(timestamp),
        nonce,
        str(hop_count),
        sha256_hex(body),
    ]).encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()

def verify_machine_request(
    *,
    body: bytes,
    key_id: str,
    timestamp: int,
    nonce: str,
    signature: str,
    hop_count: int,
    keys: Mapping[str, bytes],
    seen_nonces: Iterable[str] = (),
    now: int | None = None,
) -> dict[str, Any]:
    require(len(body) <= MAX_BODY_BYTES, "MACHINE_BODY_TOO_LARGE")
    require(key_id in keys, "MACHINE_KEY_UNKNOWN")
    require(bool(nonce) and len(nonce) <= 128, "MACHINE_NONCE_INVALID")
    require(nonce not in set(seen_nonces), "MACHINE_NONCE_REPLAY")
    require(0 <= int(hop_count) <= MAX_HOPS, "MACHINE_HOP_LIMIT_EXCEEDED")
    current = int(time.time()) if now is None else int(now)
    require(abs(current - int(timestamp)) <= MAX_CLOCK_SKEW_SECONDS, "MACHINE_TIMESTAMP_OUTSIDE_WINDOW")
    expected = machine_signature(
        key=keys[key_id], key_id=key_id, timestamp=int(timestamp),
        nonce=nonce, body=body, hop_count=int(hop_count),
    )
    require(hmac.compare_digest(str(signature), expected), "MACHINE_SIGNATURE_INVALID")
    try:
        value = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise TelegramGatewayError("MACHINE_JSON_INVALID") from exc
    require(isinstance(value, dict), "MACHINE_JSON_OBJECT_REQUIRED")
    return {
        "principal_id": f"machine:key:{key_id}",
        "principal_kind": "MACHINE",
        "nonce": nonce,
        "idempotency_key": str(value.get("idempotency_key") or "").strip(),
        "hop_count": int(hop_count),
        "payload": value,
    }

def evaluate_abuse_gate(
    *,
    principal_id: str,
    idempotency_key: str,
    seen_idempotency: Mapping[str, Mapping[str, Any]],
    principals_with_free_search: Iterable[str],
    active_principals: Iterable[str],
    last_order_unix: Mapping[str, int],
    now: int,
    sku: str,
    global_first_free_today: int,
) -> dict[str, Any]:
    require(bool(principal_id), "PRINCIPAL_REQUIRED")
    require(bool(idempotency_key), "IDEMPOTENCY_KEY_REQUIRED")
    if idempotency_key in seen_idempotency:
        prior = dict(seen_idempotency[idempotency_key])
        return {"admitted": True, "replay": True, "reason": "IDEMPOTENT_REPLAY", "prior_receipt": prior}

    require(principal_id not in set(active_principals), "ONE_ACTIVE_ORDER_PER_PRINCIPAL")
    previous = int(last_order_unix.get(principal_id, 0) or 0)
    require(previous == 0 or now - previous >= 30, "ORDER_COOLDOWN_ACTIVE")

    if sku == "JANUS.SEARCH":
        require(principal_id not in set(principals_with_free_search), "FIRST_FREE_SEARCH_ALREADY_USED")
        require(global_first_free_today < 20, "GLOBAL_FIRST_FREE_DAILY_CAP_REACHED")
        return {"admitted": True, "replay": False, "reason": "FIRST_FREE_SEARCH_ADMITTED", "price": 0}

    raise TelegramGatewayError("SPECIALIST_SKU_NOT_PUBLIC_LIVE")

__all__ = [
    "MAX_BODY_BYTES","MAX_CLOCK_SKEW_SECONDS","MAX_HOPS","MAX_TEXT_BYTES",
    "TelegramGatewayError","evaluate_abuse_gate","machine_signature",
    "normalize_telegram_update","sha256_hex","verify_machine_request",
    "verify_telegram_webhook_secret",
]
