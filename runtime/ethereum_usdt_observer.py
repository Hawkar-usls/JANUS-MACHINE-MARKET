"""Ethereum/USDT payment observation for JANUS MACHINE MARKET.

Pure stdlib JSON-RPC. The observer never signs or sends transactions. It filters
canonical USDT Transfer logs for an exact quote recipient+amount, returns a
machine-readable observation, and quarantines ambiguity instead of selecting a
payment heuristically.
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any, Iterable

from runtime.commerce_authority import CHAIN_ID, MIN_CONFIRMATIONS, USDT_ETHEREUM, CommerceInvalid, normalize_address

TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class RpcError(RuntimeError):
    pass


def hex_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value.startswith("0x"):
        raise CommerceInvalid("expected hex quantity")
    return int(value, 16)


def address_topic(address: str) -> str:
    raw = normalize_address(address)[2:]
    return "0x" + ("0" * 24) + raw


def log_index(log: dict[str, Any]) -> int:
    return hex_int(log.get("logIndex"))


def payment_reference(log: dict[str, Any]) -> str:
    tx_hash = str(log.get("transactionHash") or "").lower()
    if not (tx_hash.startswith("0x") and len(tx_hash) == 66):
        raise CommerceInvalid("invalid transaction hash in log")
    return f"{tx_hash}:{log_index(log)}"


def transfer_amount(log: dict[str, Any]) -> int:
    return hex_int(log.get("data"))


def transfer_to(log: dict[str, Any]) -> str:
    topics = log.get("topics") or []
    if len(topics) < 3:
        raise CommerceInvalid("Transfer log missing indexed recipient")
    topic = str(topics[2]).lower()
    if not (topic.startswith("0x") and len(topic) == 66):
        raise CommerceInvalid("invalid recipient topic")
    return "0x" + topic[-40:]


def is_exact_quote_transfer(log: dict[str, Any], quote: dict[str, Any]) -> bool:
    try:
        if bool(log.get("removed", False)):
            return False
        if normalize_address(log.get("address")) != normalize_address(quote["token_contract"]):
            return False
        topics = log.get("topics") or []
        if not topics or str(topics[0]).lower() != TRANSFER_TOPIC0:
            return False
        if normalize_address(transfer_to(log)) != normalize_address(quote["receiving_address"]):
            return False
        if transfer_amount(log) != int(quote["amount_usdt_micros"]):
            return False
        payment_reference(log)
        hex_int(log.get("blockNumber"))
        return True
    except (KeyError, TypeError, ValueError, CommerceInvalid):
        return False


def exact_matches(logs: Iterable[dict[str, Any]], quote: dict[str, Any]) -> list[dict[str, Any]]:
    return [log for log in logs if is_exact_quote_transfer(log, quote)]


def observe_from_logs(
    *,
    quote: dict[str, Any],
    logs: Iterable[dict[str, Any]],
    latest_block: int,
    canonical_block_hash: str | None = None,
) -> dict[str, Any]:
    matches = exact_matches(logs, quote)
    base = {
        "schema": "janus.machine_market.payment_receipt.v1",
        "quote_hash": quote.get("quote_hash"),
        "chain_id": CHAIN_ID,
        "token_contract": normalize_address(quote["token_contract"]),
        "to": normalize_address(quote["receiving_address"]),
        "amount_usdt_micros": int(quote["amount_usdt_micros"]),
        "required_confirmations": MIN_CONFIRMATIONS,
    }
    if not matches:
        return {**base, "status": "NOT_FOUND", "confirmations": 0}
    if len(matches) != 1:
        return {
            **base,
            "status": "QUARANTINED",
            "reason": "AMBIGUOUS_MULTIPLE_EXACT_TRANSFERS",
            "confirmations": 0,
            "candidate_payment_references": [payment_reference(x) for x in matches],
        }

    log = matches[0]
    block_number = hex_int(log["blockNumber"])
    block_hash = str(log.get("blockHash") or "").lower()
    if canonical_block_hash and block_hash != canonical_block_hash.lower():
        return {
            **base,
            "status": "QUARANTINED",
            "reason": "BLOCK_HASH_NOT_CANONICAL",
            "confirmations": 0,
            "tx_hash": str(log["transactionHash"]).lower(),
            "log_index": log_index(log),
            "payment_reference": payment_reference(log),
            "block_number": block_number,
            "block_hash": block_hash,
        }
    confirmations = max(0, int(latest_block) - block_number + 1)
    status = "CONFIRMED" if confirmations >= MIN_CONFIRMATIONS else "OBSERVED"
    return {
        **base,
        "status": status,
        "tx_hash": str(log["transactionHash"]).lower(),
        "log_index": log_index(log),
        "payment_reference": payment_reference(log),
        "block_number": block_number,
        "block_hash": block_hash,
        "confirmations": confirmations,
    }


class JsonRpc:
    def __init__(self, url: str, timeout: float = 15.0):
        if not url.startswith(("https://", "http://")):
            raise ValueError("RPC URL must be HTTP(S)")
        self.url = url
        self.timeout = timeout
        self._id = 0

    def call(self, method: str, params: list[Any]) -> Any:
        self._id += 1
        payload = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.url, data=payload, headers={"content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.load(response)
        except Exception as exc:  # network boundary
            raise RpcError(f"RPC request failed: {exc}") from exc
        if data.get("error"):
            raise RpcError(f"RPC error: {data['error']}")
        if "result" not in data:
            raise RpcError("RPC response missing result")
        return data["result"]


def scan_quote(rpc: JsonRpc, quote: dict[str, Any], *, from_block: int, to_block: int | None = None) -> dict[str, Any]:
    chain_id = hex_int(rpc.call("eth_chainId", []))
    if chain_id != CHAIN_ID:
        raise CommerceInvalid(f"wrong RPC chain id: {chain_id}")
    latest = hex_int(rpc.call("eth_blockNumber", []))
    end = latest if to_block is None else min(int(to_block), latest)
    if from_block < 0 or from_block > end:
        raise CommerceInvalid("invalid scan block range")
    params = [{
        "fromBlock": hex(from_block),
        "toBlock": hex(end),
        "address": normalize_address(USDT_ETHEREUM),
        "topics": [TRANSFER_TOPIC0, None, address_topic(quote["receiving_address"])],
    }]
    logs = rpc.call("eth_getLogs", params)
    matches = exact_matches(logs, quote)
    canonical_hash = None
    if len(matches) == 1:
        bn = hex_int(matches[0]["blockNumber"])
        block = rpc.call("eth_getBlockByNumber", [hex(bn), False])
        canonical_hash = str((block or {}).get("hash") or "")
    return observe_from_logs(quote=quote, logs=logs, latest_block=latest, canonical_block_hash=canonical_hash)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc-url", required=True)
    ap.add_argument("--quote", required=True, help="Path to exact quote JSON")
    ap.add_argument("--from-block", required=True, type=int)
    ap.add_argument("--to-block", type=int)
    args = ap.parse_args()
    with open(args.quote, "r", encoding="utf-8") as fh:
        quote = json.load(fh)
    result = scan_quote(JsonRpc(args.rpc_url), quote, from_block=args.from_block, to_block=args.to_block)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
