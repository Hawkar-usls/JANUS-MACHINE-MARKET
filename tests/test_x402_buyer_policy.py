import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_buyer_pilot_is_separate_from_seller_and_foreign_witness():
    policy = load("X402_BUYER_POLICY.json")
    witness = load("FOREIGN_AGENT_WITNESS.json")

    assert policy["status"] == "OWNER_AUTHORIZED_BOUNDED_BUYER_PILOT_ENABLED"
    assert policy["separation_law"]["external_buyer_spend_enabled"] is True
    assert policy["separation_law"]["seller_money_enabled"] is False
    assert policy["separation_law"]["foreign_agent_witness_required_for_buyer_call"] is False
    assert policy["separation_law"]["buyer_call_can_promote_foreign_agent_witness"] is False
    assert policy["separation_law"]["buyer_call_can_enable_paid_janus_search"] is False

    assert witness["foreign_agent_witness"] is False
    assert witness["money_enabled"] is False
    assert policy["foreign_agent_witness"]["expected_during_this_pilot"] is False
    assert policy["foreign_agent_witness"]["this_pilot_is_a_nonqualifier"] is True


def test_mach_pilot_is_exactly_bounded():
    policy = load("X402_BUYER_POLICY.json")
    pilot = policy["pilot"]

    assert pilot["method"] == "GET"
    assert pilot["resource"] == "https://api.mach.gallery/api/base/block-number"
    assert pilot["network"] == "eip155:8453"
    assert pilot["asset"]["symbol"] == "USDC"
    assert pilot["asset"]["contract"].lower() == "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
    assert pilot["asset"]["decimals"] == 6
    assert pilot["max_atomic_per_payment"] == 5000
    assert pilot["max_atomic_per_24h"] == 5000
    assert pilot["max_calls_per_24h"] == 1
    assert pilot["allowed_hosts"] == ["api.mach.gallery"]
    assert pilot["allowed_paths"] == ["/api/base/block-number"]
    assert pilot["allowed_methods"] == ["GET"]


def test_no_repository_private_key_contract():
    policy = load("X402_BUYER_POLICY.json")
    signer = policy["signer"]

    assert signer["private_key_in_repository"] is False
    assert signer["adapter"] == "CDP_MANAGED_X402_CLIENT"
    assert signer["required_environment_secrets"] == [
        "CDP_API_KEY_ID",
        "CDP_API_KEY_SECRET",
        "CDP_WALLET_SECRET",
    ]
