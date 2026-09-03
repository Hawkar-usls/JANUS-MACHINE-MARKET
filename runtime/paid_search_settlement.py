#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from runtime.commerce_authority import (
    MIN_CONFIRMATIONS,
    CommerceBlocked,
    CommerceInvalid,
    normalize_address,
    receipt_payment_reference,
    verify_payment_receipt,
)
from runtime.ethereum_usdt_observer import JsonRpc, RpcError, observe_transaction
from runtime.paid_search_checkout import settle_invoice
from runtime.paid_search_packet import build_paid_home_packet, verify_paid_home_packet
from runtime.purchase_ledger import consumed_payment_references, payment_key, persist_purchase

DEFAULT_RPC_URLS = (
    "https://ethereum-rpc.publicnode.com",
    "https://rpc.solidrpc.io/public/evm/1",
    "https://rpc.nodeflare.app/eth/public",
)
RPC_QUORUM = 2
PAYMENT_IDENTITY_FIELDS = (
    "quote_hash",
    "chain_id",
    "token_contract",
    "to",
    "amount_usdt_micros",
    "tx_hash",
    "log_index",
    "payment_reference",
    "block_number",
    "block_hash",
    "block_timestamp",
)


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CommerceInvalid(f"expected object: {path}")
    return value


def _rpc_label(url: str) -> str:
    parsed = urlparse(str(url))
    return parsed.netloc or parsed.path or "rpc"


def _base_observation(quote: dict[str, Any], *, status: str, confirmations: int = 0, reason: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema": "janus.machine_market.payment_receipt.v1",
        "quote_hash": quote.get("quote_hash"),
        "chain_id": int(quote.get("chain_id", -1)),
        "token_contract": normalize_address(quote.get("token_contract")),
        "to": normalize_address(quote.get("receiving_address")),
        "amount_usdt_micros": int(quote.get("amount_usdt_micros", -1)),
        "required_confirmations": MIN_CONFIRMATIONS,
        "status": status,
        "confirmations": max(0, int(confirmations)),
    }
    if reason:
        out["reason"] = reason[:160]
    return out


def _payment_identity(observation: dict[str, Any]) -> tuple[Any, ...]:
    values: list[Any] = []
    for field in PAYMENT_IDENTITY_FIELDS:
        value = observation.get(field)
        if field in {"token_contract", "to", "tx_hash", "payment_reference", "block_hash"} and isinstance(value, str):
            value = value.lower()
        values.append(value)
    return tuple(values)


def consensus_payment_observation(
    quote: dict[str, Any],
    observations: Iterable[tuple[str, dict[str, Any]]],
    *,
    required_quorum: int = RPC_QUORUM,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Conservatively combine independent read-only RPC observations.

    Network failures are excluded before this function. Settlement can only become
    CONFIRMED when at least `required_quorum` providers return the same immutable
    payment identity and every agreeing provider independently reaches the minimum
    confirmation threshold. A conflicting payment-bearing observation quarantines
    the proof instead of majority-selecting a payment.
    """
    rows = [(str(label), dict(obs)) for label, obs in observations if isinstance(obs, dict)]
    quorum = {
        "schema": "janus.machine_market.rpc_quorum.v1",
        "required": int(required_quorum),
        "healthy": len(rows),
        "agreeing_payment_observers": 0,
        "providers": [label for label, _ in rows],
        "status": "PENDING",
    }
    if required_quorum < 2:
        raise CommerceInvalid("RPC quorum must be at least two")
    if len(rows) < required_quorum:
        quorum["status"] = "UNAVAILABLE"
        return _base_observation(quote, status="QUARANTINED", reason="RPC_QUORUM_UNAVAILABLE"), quorum

    for _, obs in rows:
        if obs.get("quote_hash") != quote.get("quote_hash"):
            quorum["status"] = "CONFLICT"
            return _base_observation(quote, status="QUARANTINED", reason="RPC_QUOTE_BINDING_CONFLICT"), quorum
        if int(obs.get("chain_id", -1)) != int(quote.get("chain_id", -2)):
            quorum["status"] = "CONFLICT"
            return _base_observation(quote, status="QUARANTINED", reason="RPC_CHAIN_CONFLICT"), quorum
        if obs.get("status") == "QUARANTINED":
            quorum["status"] = "PROVIDER_QUARANTINE"
            return _base_observation(quote, status="QUARANTINED", reason="RPC_PROVIDER_QUARANTINE"), quorum

    payment_rows = [(label, obs) for label, obs in rows if obs.get("status") in {"OBSERVED", "CONFIRMED"}]
    if not payment_rows:
        quorum["status"] = "NOT_FOUND"
        return _base_observation(quote, status="NOT_FOUND"), quorum
    if len(payment_rows) < required_quorum:
        quorum["status"] = "PAYMENT_QUORUM_UNAVAILABLE"
        return _base_observation(quote, status="QUARANTINED", reason="RPC_PAYMENT_QUORUM_UNAVAILABLE"), quorum

    identity = _payment_identity(payment_rows[0][1])
    if any(_payment_identity(obs) != identity for _, obs in payment_rows[1:]):
        quorum["status"] = "CONFLICT"
        return _base_observation(quote, status="QUARANTINED", reason="RPC_OBSERVATION_CONFLICT"), quorum

    agreeing = len(payment_rows)
    min_confirmations = min(int(obs.get("confirmations", 0)) for _, obs in payment_rows)
    quorum["agreeing_payment_observers"] = agreeing
    quorum["min_confirmations_observed"] = min_confirmations
    quorum["status"] = "CONFIRMED" if min_confirmations >= MIN_CONFIRMATIONS else "OBSERVED"

    aggregate = dict(payment_rows[0][1])
    aggregate["confirmations"] = min_confirmations
    aggregate["required_confirmations"] = MIN_CONFIRMATIONS
    aggregate["status"] = quorum["status"]
    aggregate.pop("reason", None)
    return aggregate, quorum


def canonical_confirmed_receipt(observation: dict[str, Any]) -> dict[str, Any]:
    """Freeze a stable settlement receipt after the 12-confirmation threshold.

    Live confirmation counts grow forever, so they cannot be part of a create-only
    replay identity. Immutable transaction/block/quote bindings are preserved while
    confirmations are pinned to the admission threshold.
    """
    if observation.get("status") != "CONFIRMED" or int(observation.get("confirmations", 0)) < MIN_CONFIRMATIONS:
        raise CommerceInvalid("confirmed observation required for canonical settlement receipt")
    required = {
        "schema", "quote_hash", "chain_id", "token_contract", "to", "amount_usdt_micros",
        "tx_hash", "log_index", "payment_reference", "block_number", "block_hash", "block_timestamp",
    }
    missing = [field for field in required if observation.get(field) is None]
    if missing:
        raise CommerceInvalid("confirmed observation missing immutable fields: " + ",".join(sorted(missing)))
    receipt = {field: observation[field] for field in required}
    receipt.update({
        "status": "CONFIRMED",
        "confirmations": MIN_CONFIRMATIONS,
        "required_confirmations": MIN_CONFIRMATIONS,
    })
    return receipt


def observe_transaction_quorum(
    *,
    quote: dict[str, Any],
    tx_hash: str,
    expected_log_index: int | None,
    rpc_urls: Iterable[str],
    required_quorum: int = RPC_QUORUM,
) -> tuple[dict[str, Any], dict[str, Any]]:
    observations: list[tuple[str, dict[str, Any]]] = []
    failures: list[dict[str, str]] = []
    urls = tuple(dict.fromkeys(str(x).strip() for x in rpc_urls if str(x).strip()))
    if len(urls) < required_quorum:
        raise CommerceInvalid("insufficient configured RPC providers for quorum")
    for url in urls:
        label = _rpc_label(url)
        try:
            observation = observe_transaction(
                JsonRpc(url), quote, tx_hash=tx_hash, expected_log_index=expected_log_index
            )
            observations.append((label, observation))
        except (RpcError, CommerceInvalid, OSError, ValueError) as exc:
            failures.append({"provider": label, "error_class": type(exc).__name__})
    aggregate, quorum = consensus_payment_observation(
        quote, observations, required_quorum=required_quorum
    )
    quorum["configured"] = len(urls)
    quorum["failures"] = failures
    return aggregate, quorum


def recover_purchase_for_payment(state_root: str | Path, payment_receipt: dict[str, Any]) -> dict[str, Any] | None:
    root = Path(state_root)
    ref = receipt_payment_reference(payment_receipt)
    payment_path = root / "state/commerce/payments" / f"{payment_key(ref)}.json"
    if not payment_path.exists():
        return None
    payment_record = _load(payment_path)
    if str(payment_record.get("payment_reference") or "").lower() != ref:
        raise CommerceInvalid("persistent payment reference mismatch")
    if payment_record.get("payment_receipt") != payment_receipt:
        raise CommerceInvalid("persistent canonical payment receipt conflict")
    purchase_id = str(payment_record.get("purchase_id") or "")
    if not purchase_id:
        raise CommerceInvalid("persistent payment record missing purchase id")
    purchase_path = root / "state/commerce/purchases" / f"{purchase_id}.json"
    if not purchase_path.exists():
        raise CommerceInvalid("persistent purchase record missing")
    purchase_record = _load(purchase_path)
    grant = purchase_record.get("purchase_grant")
    if not isinstance(grant, dict):
        raise CommerceInvalid("persistent purchase grant missing")
    if grant.get("purchase_id") != purchase_id or grant.get("payment_reference") != ref:
        raise CommerceInvalid("persistent purchase binding mismatch")
    return grant


def settle_proof(
    *,
    invoice_record: dict[str, Any],
    proof: dict[str, Any],
    state_root: str | Path,
    rpc_urls: Iterable[str],
    readiness: dict[str, Any],
    witness: dict[str, Any],
    product: dict[str, Any],
) -> dict[str, Any]:
    request = invoice_record.get("request")
    invoice = invoice_record.get("invoice")
    if not isinstance(request, dict) or not isinstance(invoice, dict):
        raise CommerceInvalid("invoice record missing request/invoice")
    tx_hash = str(proof.get("tx_hash") or "")
    log_index = proof.get("log_index")
    if log_index is not None:
        log_index = int(log_index)

    observation, rpc_quorum = observe_transaction_quorum(
        quote=invoice["quote"],
        tx_hash=tx_hash,
        expected_log_index=log_index,
        rpc_urls=rpc_urls,
    )
    result: dict[str, Any] = {
        "schema": "janus.machine_market.paid_search_settlement_result.v1",
        "invoice_id": invoice["invoice_id"],
        "observation": observation,
        "rpc_quorum": rpc_quorum,
        "settled": False,
    }
    if observation.get("status") != "CONFIRMED":
        return result

    payment_receipt = canonical_confirmed_receipt(observation)
    verify_payment_receipt(invoice["quote"], payment_receipt)
    recovered = recover_purchase_for_payment(state_root, payment_receipt)
    if recovered is not None:
        grant = recovered
        packet = build_paid_home_packet(
            request=request,
            purchase_grant=grant,
            quote=invoice["quote"],
            payment_receipt=payment_receipt,
        )
        ledger = {"payment": "IDEMPOTENT_REPLAY", "purchase": "IDEMPOTENT_REPLAY"}
        replayed = True
    else:
        grant, packet = settle_invoice(
            invoice=invoice,
            request=request,
            payment_receipt=payment_receipt,
            readiness=readiness,
            witness=witness,
            product=product,
            consumed_payment_refs=consumed_payment_references(state_root),
        )
        ledger = persist_purchase(state_root, payment_receipt, grant)
        replayed = False
    if not verify_paid_home_packet(packet):
        raise CommerceInvalid("paid HOME packet self-verification failed")
    return {
        **result,
        "settled": True,
        "replayed": replayed,
        "purchase_id": grant["purchase_id"],
        "purchase_grant_hash": grant["grant_hash"],
        "payment_reference": grant["payment_reference"],
        "canonical_payment_receipt": payment_receipt,
        "query_id": packet["query_id"],
        "packet_hash": packet["packet_hash"],
        "ledger": ledger,
        "packet": packet,
    }


def _public_result(out: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in out.items() if k != "packet"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--invoice-record", required=True)
    ap.add_argument("--proof", required=True)
    ap.add_argument("--state-root", required=True)
    ap.add_argument("--rpc-url", action="append", dest="rpc_urls")
    ap.add_argument("--readiness", required=True)
    ap.add_argument("--witness", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--result-out", required=True)
    ap.add_argument("--packet-out", required=True)
    args = ap.parse_args()
    invoice_record = _load(args.invoice_record)
    rpc_urls = tuple(args.rpc_urls or DEFAULT_RPC_URLS)
    try:
        out = settle_proof(
            invoice_record=invoice_record,
            proof=_load(args.proof),
            state_root=args.state_root,
            rpc_urls=rpc_urls,
            readiness=_load(args.readiness),
            witness=_load(args.witness),
            product=_load(args.product),
        )
    except (CommerceInvalid, CommerceBlocked) as exc:
        invoice = invoice_record.get("invoice") or {}
        reason = str(exc).replace("\n", " ")[:160]
        out = {
            "schema": "janus.machine_market.paid_search_settlement_result.v1",
            "invoice_id": str(invoice.get("invoice_id") or ""),
            "observation": {"status": "REJECTED", "confirmations": 0, "reason": reason},
            "settled": False,
            "reason": reason,
        }
    public = _public_result(out)
    Path(args.result_out).write_text(
        json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if out.get("settled"):
        Path(args.packet_out).write_text(
            json.dumps(out["packet"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(public, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
