#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

from runtime.commerce_authority import BTT_RECEIVER, BTT_TRON, CommerceInvalid

TRONGRID_BASE = "https://api.trongrid.io"
TRANSFER_TOPIC = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class TronRpcError(RuntimeError): pass


def _b58decode_check(value: str) -> bytes:
    n = 0
    for ch in str(value):
        try: idx = B58_ALPHABET.index(ch)
        except ValueError as exc: raise CommerceInvalid("invalid TRON base58 address") from exc
        n = n * 58 + idx
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = b"\x00" * (len(value) - len(value.lstrip("1"))) + raw
    if len(raw) < 5: raise CommerceInvalid("invalid TRON base58check length")
    payload, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected: raise CommerceInvalid("invalid TRON base58check checksum")
    if len(payload) != 21 or payload[0] != 0x41: raise CommerceInvalid("invalid TRON mainnet address payload")
    return payload


def tron_hex20(address: str) -> str: return _b58decode_check(address)[1:].hex()


def _norm_hex(value: Any) -> str:
    text = str(value or "").lower().removeprefix("0x")
    try: int(text or "0", 16)
    except ValueError as exc: raise CommerceInvalid("invalid hex field in TRON receipt") from exc
    return text


def _log_hex20(value: Any) -> str:
    text = _norm_hex(value)
    if len(text) == 42 and text.startswith("41"): text = text[2:]
    if len(text) != 40: raise CommerceInvalid("unexpected TRON event address length")
    return text


def _iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class TronHttp:
    def __init__(self, base_url: str = TRONGRID_BASE, api_key: str | None = None, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("TRON_PRO_API_KEY")
        self.timeout = timeout

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type":"application/json","Accept":"application/json","User-Agent":"JANUS-MACHINE-MARKET/1.0"}
        if self.api_key: headers["TRON-PRO-API-KEY"] = self.api_key
        req = Request(self.base_url + path, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise TronRpcError(f"TRON RPC failed for {path}: {type(exc).__name__}") from exc
        if not isinstance(payload, dict): raise TronRpcError("TRON RPC returned non-object")
        if payload.get("Error"): raise TronRpcError("TRON RPC returned Error")
        return payload


def _txid(value: Any) -> str:
    text = str(value or "").strip().lower().removeprefix("0x")
    if len(text) != 64: raise CommerceInvalid("invalid TRON txid")
    try: int(text, 16)
    except ValueError as exc: raise CommerceInvalid("invalid TRON txid") from exc
    return text


def _success_body(body: dict[str, Any], txid: str) -> None:
    got = str(body.get("txID") or body.get("txid") or "").lower().removeprefix("0x")
    if got != txid: raise CommerceInvalid("solidified TRON transaction body mismatch")
    ret = body.get("ret") or []
    if ret:
        contract_ret = str((ret[0] or {}).get("contractRet") or "")
        if contract_ret != "SUCCESS": raise CommerceInvalid("solidified TRON contractRet is not SUCCESS")


def _success_receipt(info: dict[str, Any], txid: str) -> None:
    got = str(info.get("id") or "").lower().removeprefix("0x")
    if got != txid: raise CommerceInvalid("solidified TRON execution receipt mismatch")
    if str(info.get("result") or "").upper() == "FAILED": raise CommerceInvalid("TRON top-level execution result FAILED")
    if str((info.get("receipt") or {}).get("result") or "") != "SUCCESS": raise CommerceInvalid("TRON receipt.result is not SUCCESS")


def _matching_transfer_logs(info: dict[str, Any], quote: dict[str, Any]) -> list[tuple[int, int]]:
    contract20 = tron_hex20(str(quote["token_contract"])); receiver20 = tron_hex20(str(quote["receiving_address"])); expected_amount = int(quote["amount_atomic"])
    matches: list[tuple[int, int]] = []
    for index, log in enumerate(info.get("log") or []):
        if not isinstance(log, dict): continue
        try:
            if _log_hex20(log.get("address")) != contract20: continue
            topics = [_norm_hex(x) for x in (log.get("topics") or [])]
            if len(topics) < 3 or topics[0].rjust(64, "0") != TRANSFER_TOPIC: continue
            if topics[2][-40:] != receiver20: continue
            amount = int(_norm_hex(log.get("data")) or "0", 16)
            if amount != expected_amount: continue
        except (CommerceInvalid, ValueError): continue
        matches.append((index, amount))
    return matches


def observe_btt_transfer(client: TronHttp, quote: dict[str, Any], *, txid: str, expected_event_index: int | None = None, observed_at: datetime | None = None) -> dict[str, Any]:
    txid = _txid(txid)
    if quote.get("asset") != "BTT" or quote.get("token_contract") != BTT_TRON or quote.get("receiving_address") != BTT_RECEIVER:
        raise CommerceInvalid("observer received non-canonical BTT quote")
    body = client.post("/walletsolidity/gettransactionbyid", {"value": txid})
    info = client.post("/walletsolidity/gettransactioninfobyid", {"value": txid})
    if not body:
        return {"schema":"janus.machine_market.btt_payment_observation.v1","status":"NOT_FOUND","quote_hash":quote.get("quote_hash"),"txid":txid,"reason":"SOLIDIFIED_TRANSACTION_BODY_NOT_FOUND"}
    if not info:
        return {"schema":"janus.machine_market.btt_payment_observation.v1","status":"OBSERVED","quote_hash":quote.get("quote_hash"),"txid":txid,"reason":"SOLIDIFIED_EXECUTION_RECEIPT_NOT_FOUND"}
    _success_body(body, txid); _success_receipt(info, txid)
    matches = _matching_transfer_logs(info, quote)
    if expected_event_index is not None: matches = [row for row in matches if row[0] == int(expected_event_index)]
    if not matches:
        return {"schema":"janus.machine_market.btt_payment_observation.v1","status":"NOT_FOUND","quote_hash":quote.get("quote_hash"),"txid":txid,"reason":"EXACT_TRC20_TRANSFER_NOT_FOUND"}
    if len(matches) != 1:
        return {"schema":"janus.machine_market.btt_payment_observation.v1","status":"QUARANTINED","quote_hash":quote.get("quote_hash"),"txid":txid,"candidate_event_indexes":[x[0] for x in matches],"reason":"MULTIPLE_EXACT_TRC20_TRANSFERS_REQUIRE_EVENT_INDEX"}
    event_index, amount = matches[0]
    block_number = int(info.get("blockNumber") or 0); block_ms = int(info.get("blockTimeStamp") or 0)
    if block_number <= 0 or block_ms <= 0: raise CommerceInvalid("solidified BTT receipt missing block identity")
    now = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc); payment_reference = f"tron:{txid}:{event_index}"
    return {
        "schema":"janus.machine_market.btt_payment_receipt.v1","status":"CONFIRMED","quote_hash":quote["quote_hash"],"asset":"BTT","network":"tron-mainnet","token_standard":"TRC-20",
        "token_contract":quote["token_contract"],"to":quote["receiving_address"],"amount_atomic":amount,"decimals":int(quote["decimals"]),
        "txid":txid,"event_index":event_index,"log_index":event_index,"payment_reference":payment_reference,"block_number":block_number,"block_timestamp":_iso_ms(block_ms),
        "solidified_transaction_body":True,"solidified_execution_receipt":True,"contract_execution_success":True,"observed_at":now.isoformat().replace("+00:00","Z"),
    }


__all__ = ["TRONGRID_BASE","TRANSFER_TOPIC","TronHttp","TronRpcError","observe_btt_transfer","tron_hex20"]
