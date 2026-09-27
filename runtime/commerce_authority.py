"""Fail-closed JANUS MACHINE MARKET commerce authority primitives.

This module deliberately does not perform network I/O. It binds
REQUEST -> QUOTE -> PAYMENT_RECEIPT -> PURCHASE_GRANT and separates
seller-commerce authorization from FOREIGN_AGENT_WITNESS evidence.

Payment evidence is rail-aware: the live seller may accept an exact verified
Ethereum-USDT receipt or an exact verified TRON-BTT receipt. Both converge on
one rail-neutral purchase grant and the same one-execution-per-purchase ledger.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

USDT_ETHEREUM = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
CHAIN_ID = 1
USDT_DECIMALS = 6
MIN_CONFIRMATIONS = 12
BTT_TRON = "TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4"
BTT_RECEIVER = "TSqkDJX9uBEnA8mmRc4UN3Bw6hcujcvmd1"
BTT_DECIMALS = 18
TRON_NETWORK = "tron-mainnet"
PAID_SEARCH_MAX_TURNS = 1
PAID_SEARCH_MAX_MESSAGE_UTF8_BYTES = 4000
PAID_SEARCH_MAX_ANSWER_UTF8_BYTES = 6000
PAID_SEARCH_HISTORY_TURNS = 0


class CommerceBlocked(RuntimeError): pass
class CommerceInvalid(ValueError): pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str: return hashlib.sha256(canonical_json(value)).hexdigest()
def utc_now() -> datetime: return datetime.now(timezone.utc)


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None: raise CommerceInvalid("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def normalize_address(value: str) -> str:
    v = str(value or "").strip()
    if not (v.startswith("0x") and len(v) == 42): raise CommerceInvalid("invalid ethereum address")
    try: int(v[2:], 16)
    except ValueError as exc: raise CommerceInvalid("invalid ethereum address") from exc
    return v.lower()


def request_hash(request: dict[str, Any]) -> str: return digest(request)
def quote_hash(quote_without_hash: dict[str, Any]) -> str: return digest(quote_without_hash)


def _hex64(value: str, *, allow_0x: bool) -> str:
    raw = str(value or "").strip().lower()
    if allow_0x and raw.startswith("0x"):
        body = raw[2:]
    else:
        body = raw
    if len(body) != 64:
        raise CommerceInvalid("invalid transaction hash")
    try: int(body, 16)
    except ValueError as exc: raise CommerceInvalid("invalid transaction hash") from exc
    return body


def receipt_payment_reference(receipt: dict[str, Any]) -> str:
    """Return canonical replay identity for any admitted payment rail."""
    if receipt.get("schema") == "janus.machine_market.btt_payment_receipt.v1" or receipt.get("asset") == "BTT":
        txid = _hex64(str(receipt.get("txid") or receipt.get("tx_hash") or ""), allow_0x=False)
        try: event_index = int(receipt["event_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CommerceInvalid("BTT payment receipt requires TRC20 event_index") from exc
        if event_index < 0: raise CommerceInvalid("invalid TRC20 event_index")
        expected = f"tron:{txid}:{event_index}"
        supplied = str(receipt.get("payment_reference") or "").lower()
        if supplied != expected: raise CommerceInvalid("payment reference mismatch")
        return expected

    tx_hash = str(receipt.get("tx_hash") or "").lower()
    if not (tx_hash.startswith("0x") and len(tx_hash) == 66): raise CommerceInvalid("invalid transaction hash")
    try: int(tx_hash[2:], 16)
    except ValueError as exc: raise CommerceInvalid("invalid transaction hash") from exc
    try: log_index = int(receipt["log_index"])
    except (KeyError, TypeError, ValueError) as exc: raise CommerceInvalid("payment receipt requires ERC20 log_index") from exc
    if log_index < 0: raise CommerceInvalid("invalid ERC20 log_index")
    expected = f"{tx_hash}:{log_index}"
    supplied = str(receipt.get("payment_reference") or "").lower()
    if supplied != expected: raise CommerceInvalid("payment reference mismatch")
    return expected


def build_quote(*, request: dict[str, Any], sku: str, amount_usdt_micros: int, receiving_address: str, expires_at: str, nonce: str, policy_version: str) -> dict[str, Any]:
    """Build the canonical Ethereum-USDT quote."""
    if amount_usdt_micros <= 0: raise CommerceInvalid("amount must be positive")
    if not sku or not nonce or not policy_version: raise CommerceInvalid("sku, nonce and policy_version are required")
    parse_time(expires_at)
    body = {
        "schema": "janus.machine_market.quote.v1", "sku": sku,
        "request_hash": request_hash(request), "amount_usdt_micros": int(amount_usdt_micros),
        "asset": "USDT", "chain_id": CHAIN_ID, "token_contract": USDT_ETHEREUM,
        "receiving_address": normalize_address(receiving_address), "expires_at": expires_at,
        "nonce": nonce, "policy_version": policy_version,
    }
    return {**body, "quote_hash": quote_hash(body)}


def verify_quote(quote: dict[str, Any], request: dict[str, Any], *, now: datetime | None = None, require_unexpired: bool = True) -> None:
    q = dict(quote); supplied_hash = q.pop("quote_hash", None)
    if not supplied_hash or supplied_hash != quote_hash(q): raise CommerceInvalid("quote hash mismatch")
    if q.get("request_hash") != request_hash(request): raise CommerceInvalid("request hash mismatch")
    asset = str(q.get("asset") or "")
    if asset == "USDT":
        if q.get("chain_id") != CHAIN_ID: raise CommerceInvalid("unsupported chain")
        if normalize_address(q.get("token_contract")) != normalize_address(USDT_ETHEREUM): raise CommerceInvalid("unexpected token contract")
        if int(q.get("amount_usdt_micros", -1)) <= 0: raise CommerceInvalid("invalid amount")
    elif asset == "BTT":
        if q.get("network") != TRON_NETWORK: raise CommerceInvalid("unsupported BTT network")
        if q.get("token_standard") != "TRC-20": raise CommerceInvalid("unexpected BTT token standard")
        if str(q.get("token_contract") or "") != BTT_TRON: raise CommerceInvalid("unexpected BTT token contract")
        if str(q.get("receiving_address") or "") != BTT_RECEIVER: raise CommerceInvalid("unexpected BTT receiver")
        if int(q.get("decimals", -1)) != BTT_DECIMALS: raise CommerceInvalid("unexpected BTT decimals")
        if int(q.get("amount_atomic", -1)) <= 0: raise CommerceInvalid("invalid BTT atomic amount")
        if int(q.get("amount_usdt_micros", -1)) <= 0: raise CommerceInvalid("invalid discounted USDT reference")
        if int(q.get("reference_usdt_micros", -1)) <= 0: raise CommerceInvalid("invalid canonical USDT reference")
        if int(q.get("discount_bps", -1)) != 5000: raise CommerceInvalid("unexpected BTT discount")
        oracle = q.get("oracle") or {}
        if oracle.get("symbol") != "BTTUSDT" or not oracle.get("price") or not oracle.get("close_time_ms"):
            raise CommerceInvalid("BTT oracle binding missing")
        if q.get("rounding") != "CEILING_TO_BTT_ATOMIC_UNIT": raise CommerceInvalid("BTT rounding rule invalid")
    else:
        raise CommerceInvalid("unexpected asset")
    expiry = parse_time(q["expires_at"])
    if require_unexpired and expiry <= (now or utc_now()): raise CommerceInvalid("quote expired")


def verify_payment_receipt(quote: dict[str, Any], receipt: dict[str, Any], *, consumed_payment_refs: Iterable[str] = ()) -> None:
    ref = receipt_payment_reference(receipt)
    if ref in {str(x).lower() for x in consumed_payment_refs}: raise CommerceInvalid("payment reference already consumed")

    if quote.get("asset") == "BTT":
        if receipt.get("schema") != "janus.machine_market.btt_payment_receipt.v1": raise CommerceInvalid("BTT payment receipt schema invalid")
        if receipt.get("status") != "CONFIRMED": raise CommerceInvalid("BTT payment is not confirmed")
        if receipt.get("asset") != "BTT" or receipt.get("network") != TRON_NETWORK: raise CommerceInvalid("BTT payment network mismatch")
        if receipt.get("token_contract") != quote.get("token_contract"): raise CommerceInvalid("BTT payment token mismatch")
        if receipt.get("to") != quote.get("receiving_address"): raise CommerceInvalid("BTT payment recipient mismatch")
        if int(receipt.get("amount_atomic", -1)) != int(quote.get("amount_atomic", -2)): raise CommerceInvalid("BTT payment amount mismatch")
        if receipt.get("quote_hash") != quote.get("quote_hash"): raise CommerceInvalid("BTT payment receipt quote binding mismatch")
        if receipt.get("solidified_transaction_body") is not True or receipt.get("solidified_execution_receipt") is not True:
            raise CommerceInvalid("BTT payment is not solidified")
        if receipt.get("contract_execution_success") is not True: raise CommerceInvalid("BTT smart-contract execution failed")
        block_timestamp = parse_time(str(receipt.get("block_timestamp") or ""))
        if block_timestamp > parse_time(quote["expires_at"]): raise CommerceInvalid("BTT payment was mined after quote expiry")
        return

    if receipt.get("schema") != "janus.machine_market.payment_receipt.v1": raise CommerceInvalid("payment receipt schema invalid")
    if receipt.get("status") != "CONFIRMED": raise CommerceInvalid("payment is not confirmed")
    if int(receipt.get("chain_id", -1)) != int(quote["chain_id"]): raise CommerceInvalid("payment chain mismatch")
    if normalize_address(receipt.get("token_contract")) != normalize_address(quote["token_contract"]): raise CommerceInvalid("payment token mismatch")
    if normalize_address(receipt.get("to")) != normalize_address(quote["receiving_address"]): raise CommerceInvalid("payment recipient mismatch")
    if int(receipt.get("amount_usdt_micros", -1)) != int(quote["amount_usdt_micros"]): raise CommerceInvalid("payment amount mismatch")
    if receipt.get("quote_hash") != quote.get("quote_hash"): raise CommerceInvalid("payment receipt quote binding mismatch")
    if int(receipt.get("required_confirmations", 0)) < MIN_CONFIRMATIONS: raise CommerceInvalid("payment receipt weakens confirmation policy")
    if int(receipt.get("confirmations", 0)) < MIN_CONFIRMATIONS: raise CommerceInvalid("payment confirmation threshold not met")
    block_timestamp = parse_time(str(receipt.get("block_timestamp") or ""))
    if block_timestamp > parse_time(quote["expires_at"]): raise CommerceInvalid("payment was mined after quote expiry")


def _paid_search_entitlement(*, purchase_id: str, buyer_actor_id: str) -> dict[str, Any]:
    actor = str(buyer_actor_id or "").strip()
    if not actor: raise CommerceInvalid("paid buyer actor id required")
    nonce = "paid-" + digest({"purchase_id": purchase_id, "buyer_actor_id": actor, "purpose": "PAID_SEARCH_BUYER_QUERY_ENTITLEMENT"})[:32]
    return {
        "enabled": True,
        "buyer_actor_id": actor,
        "max_turns": PAID_SEARCH_MAX_TURNS,
        "max_message_utf8_bytes": PAID_SEARCH_MAX_MESSAGE_UTF8_BYTES,
        "max_answer_utf8_bytes": PAID_SEARCH_MAX_ANSWER_UTF8_BYTES,
        "conversation_history_turns": PAID_SEARCH_HISTORY_TURNS,
        "entitlement_nonce": nonce,
        "read_only_conversation": True,
        "external_effect_authorized": False,
    }


def admit_purchase(*, readiness: dict[str, Any], foreign_witness: dict[str, Any], product: dict[str, Any], request: dict[str, Any], quote: dict[str, Any], payment_receipt: dict[str, Any], consumed_payment_refs: Iterable[str] = (), now: datetime | None = None, buyer_actor_id: str | None = None) -> dict[str, Any]:
    """Return deterministic rail-neutral PURCHASE_GRANT, never EXECUTION_GRANT."""
    if readiness.get("seller_commerce_authorized") is not True: raise CommerceBlocked("seller commerce is not authorized")
    if readiness.get("money_enabled") is not True: raise CommerceBlocked("money_enabled is false")
    if readiness.get("autonomous_purchase_declared") is not True: raise CommerceBlocked("autonomous purchase is not declared")
    if foreign_witness.get("foreign_agent_witness") not in (True, False): raise CommerceBlocked("foreign agent witness state is malformed")
    if product.get("machine_purchase") is not True: raise CommerceBlocked("product is not machine-purchasable")
    if quote.get("sku") != product.get("sku"): raise CommerceInvalid("quote/product SKU mismatch")

    verify_quote(quote, request, now=now, require_unexpired=False)
    verify_payment_receipt(quote, payment_receipt, consumed_payment_refs=consumed_payment_refs)
    payment_ref = receipt_payment_reference(payment_receipt)
    seed = {"quote_hash": quote["quote_hash"], "request_hash": quote["request_hash"], "sku": quote["sku"], "payment_reference": payment_ref, "policy_version": quote["policy_version"]}
    purchase_id = "jp-" + digest(seed)[:40]
    entitlement = _paid_search_entitlement(purchase_id=purchase_id, buyer_actor_id=buyer_actor_id) if quote["sku"] == "JANUS.SEARCH" and buyer_actor_id else None
    grant = {
        "schema": "janus.machine_market.purchase_grant.v1",
        "purchase_id": purchase_id,
        "sku": quote["sku"],
        "offer_hash": None,
        "quote_hash": quote["quote_hash"],
        "request_hash": quote["request_hash"],
        "terms_hash": None,
        "payment_reference": payment_ref,
        "amount_usdt_micros": int(quote["amount_usdt_micros"]),
        "payment_asset": str(quote.get("asset") or ""),
        "payment_network": str(quote.get("network") or ("ethereum-mainnet" if quote.get("asset") == "USDT" else "")),
        "payment_amount_atomic": int(quote.get("amount_atomic") if quote.get("asset") == "BTT" else quote["amount_usdt_micros"]),
        "reference_usdt_micros": int(quote.get("reference_usdt_micros") or quote["amount_usdt_micros"]),
        "policy_version": quote["policy_version"],
        "status": "PURCHASE_SETTLED",
        "execution_authority_granted": False,
        "allowed_operation": "REQUEST_BOUNDED_BUYER_QUERY" if entitlement else "REQUEST_BOUNDED_EXECUTION_GRANT",
        "next_gate": "JANUS_HOME_READ_ONLY_BUYER_QUERY" if entitlement else "JANUS_POLICY_SCOPE_TO_EXECUTION_GRANT",
        "authority_ceiling": {"sku": quote["sku"], "production_activator_authority": False, "external_effect_authority": False},
        "buyer_query_entitlement": entitlement,
        "foreign_agent_witness_at_purchase": bool(foreign_witness.get("foreign_agent_witness")),
        "foreign_agent_witness_required_for_purchase": False,
        "expires_at": None,
        "reasons": ["PAYMENT_CONFIRMED_PURCHASE_GRANT_IS_NOT_EXECUTION_AUTHORITY"],
    }
    grant["grant_hash"] = digest(grant)
    return grant
