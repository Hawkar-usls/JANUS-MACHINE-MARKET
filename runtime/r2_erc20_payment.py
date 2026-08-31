#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
RECEIPT_SCHEMA = "janus.machine_market.payment_receipt.v1"


class PaymentVerificationError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PaymentVerificationError(code)


def norm_address(value: str) -> str:
    text = str(value or "").lower()
    require(text.startswith("0x") and len(text) == 42 and all(c in "0123456789abcdef" for c in text[2:]), "ADDRESS_INVALID")
    return text


def norm_tx_hash(value: str) -> str:
    text = str(value or "").lower()
    require(text.startswith("0x") and len(text) == 66 and all(c in "0123456789abcdef" for c in text[2:]), "TX_HASH_INVALID")
    return text


def _topic_address(topic: str) -> str:
    text = str(topic or "").lower()
    require(text.startswith("0x") and len(text) == 66, "ERC20_TOPIC_ADDRESS_INVALID")
    return norm_address("0x" + text[-40:])


def _hex_int(value: str, code: str) -> int:
    try:
        return int(str(value), 16)
    except Exception as exc:  # noqa: BLE001
        raise PaymentVerificationError(code) from exc


def _rpc(url: str, method: str, params: list[Any], timeout: int = 15) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json", "user-agent": "JANUS-MACHINE-MARKET/1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error") is not None:
        raise PaymentVerificationError(f"RPC_ERROR:{method}")
    return payload.get("result")


@dataclass(frozen=True)
class TransferEvidence:
    tx_hash: str
    block_hash: str
    block_number: int
    log_index: int
    from_address: str
    to_address: str
    amount_atomic: int
    confirmations: int

    def agreement_key(self) -> tuple[Any, ...]:
        return (
            self.tx_hash,
            self.block_hash,
            self.block_number,
            self.log_index,
            self.from_address,
            self.to_address,
            self.amount_atomic,
        )


def parse_exact_transfer(
    *,
    receipt: dict[str, Any],
    current_block: int,
    tx_hash: str,
    token_contract: str,
    expected_to: str,
    expected_amount_atomic: int,
    minimum_confirmations: int,
) -> TransferEvidence:
    require(isinstance(receipt, dict), "TX_RECEIPT_MISSING")
    require(_hex_int(receipt.get("status", "0x0"), "TX_STATUS_INVALID") == 1, "TX_RECEIPT_NOT_SUCCESS")
    receipt_tx = norm_tx_hash(receipt.get("transactionHash"))
    require(receipt_tx == tx_hash, "TX_RECEIPT_HASH_MISMATCH")
    block_hash = str(receipt.get("blockHash") or "").lower()
    require(block_hash.startswith("0x") and len(block_hash) == 66, "BLOCK_HASH_INVALID")
    block_number = _hex_int(receipt.get("blockNumber"), "BLOCK_NUMBER_INVALID")
    confirmations = current_block - block_number + 1
    require(confirmations >= minimum_confirmations, "PAYMENT_CONFIRMATIONS_INSUFFICIENT")

    matches: list[TransferEvidence] = []
    for log in receipt.get("logs") or []:
        if not isinstance(log, dict):
            continue
        try:
            address = norm_address(log.get("address"))
        except PaymentVerificationError:
            continue
        if address != token_contract:
            continue
        topics = log.get("topics") or []
        if len(topics) < 3 or str(topics[0]).lower() != TRANSFER_TOPIC:
            continue
        try:
            from_address = _topic_address(topics[1])
            to_address = _topic_address(topics[2])
            amount = _hex_int(log.get("data"), "ERC20_AMOUNT_INVALID")
            log_index = _hex_int(log.get("logIndex"), "ERC20_LOG_INDEX_INVALID")
        except PaymentVerificationError:
            continue
        if to_address != expected_to or amount != expected_amount_atomic:
            continue
        matches.append(TransferEvidence(
            tx_hash=tx_hash,
            block_hash=block_hash,
            block_number=block_number,
            log_index=log_index,
            from_address=from_address,
            to_address=to_address,
            amount_atomic=amount,
            confirmations=confirmations,
        ))
    require(len(matches) == 1, "EXACT_ERC20_TRANSFER_MATCH_COUNT_NOT_ONE")
    return matches[0]


def verify_payment(
    *,
    tx_hash: str,
    route: dict[str, Any],
    expected_amount_atomic: int,
    rpc_urls: list[str],
) -> dict[str, Any]:
    tx_hash = norm_tx_hash(tx_hash)
    require(isinstance(expected_amount_atomic, int) and not isinstance(expected_amount_atomic, bool) and expected_amount_atomic > 0, "EXPECTED_AMOUNT_INVALID")
    network = route.get("network") or {}
    asset = route.get("asset") or {}
    merchant = route.get("merchant") or {}
    verification = route.get("verification") or {}
    require(network.get("chain_id") == 1, "PAYMENT_ROUTE_CHAIN_UNSUPPORTED")
    require(asset.get("symbol") == "USDT" and asset.get("standard") == "ERC20", "PAYMENT_ROUTE_ASSET_UNSUPPORTED")
    token_contract = norm_address(asset.get("contract"))
    expected_to = norm_address(merchant.get("receiving_address"))
    minimum_confirmations = int(verification.get("minimum_confirmations", 12))
    quorum = int(verification.get("rpc_quorum", 2))
    urls = list(dict.fromkeys(u.strip() for u in rpc_urls if str(u).strip()))
    require(len(urls) >= quorum >= 1, "RPC_QUORUM_NOT_CONFIGURED")

    evidence: list[TransferEvidence] = []
    errors: list[str] = []
    for url in urls:
        try:
            chain_id = _hex_int(_rpc(url, "eth_chainId", []), "RPC_CHAIN_ID_INVALID")
            require(chain_id == 1, "RPC_CHAIN_ID_MISMATCH")
            receipt = _rpc(url, "eth_getTransactionReceipt", [tx_hash])
            current_block = _hex_int(_rpc(url, "eth_blockNumber", []), "RPC_BLOCK_NUMBER_INVALID")
            evidence.append(parse_exact_transfer(
                receipt=receipt,
                current_block=current_block,
                tx_hash=tx_hash,
                token_contract=token_contract,
                expected_to=expected_to,
                expected_amount_atomic=expected_amount_atomic,
                minimum_confirmations=minimum_confirmations,
            ))
        except Exception as exc:  # noqa: BLE001
            errors.append(type(exc).__name__ + ":" + str(exc))

    require(len(evidence) >= quorum, "RPC_QUORUM_NO_VERIFIABLE_PAYMENT")
    counts = Counter(e.agreement_key() for e in evidence)
    key, count = counts.most_common(1)[0]
    require(count >= quorum, "RPC_QUORUM_PAYMENT_DISAGREEMENT")
    agreed = [e for e in evidence if e.agreement_key() == key]
    chosen = min(agreed, key=lambda e: e.confirmations)
    payment_reference = f"ethereum:1:{chosen.tx_hash}:{chosen.log_index}"
    out = {
        "schema": RECEIPT_SCHEMA,
        "route_id": route.get("route_id"),
        "chain_id": 1,
        "asset": "USDT",
        "token_contract": token_contract,
        "tx_hash": chosen.tx_hash,
        "block_hash": chosen.block_hash,
        "block_number": chosen.block_number,
        "log_index": chosen.log_index,
        "from_address": chosen.from_address,
        "to_address": chosen.to_address,
        "amount_atomic": chosen.amount_atomic,
        "confirmations": chosen.confirmations,
        "rpc_quorum": quorum,
        "rpc_provider_count": len(agreed),
        "verification_status": "VERIFIED_EXACT_ERC20_TRANSFER",
        "payment_reference": payment_reference,
    }
    out["receipt_hash"] = digest(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an exact USDT/ERC20 payment for JANUS Machine Market")
    parser.add_argument("--tx-hash", required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--amount-atomic", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    route = json.loads(Path(args.route).read_text(encoding="utf-8"))
    urls = [u for u in os.environ.get("JANUS_ETH_RPC_URLS", "").split(",") if u.strip()]
    receipt = verify_payment(tx_hash=args.tx_hash, route=route, expected_amount_atomic=args.amount_atomic, rpc_urls=urls)
    Path(args.output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("R2_PAYMENT_VERIFIED=PASS")
    print("PAYMENT_REFERENCE=" + receipt["payment_reference"])
    print("PAYMENT_RECEIPT_HASH=" + receipt["receipt_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
