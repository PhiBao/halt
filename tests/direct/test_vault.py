"""Direct tests for HaltVault (standalone: zero guardian skips cross checks)."""
import json

import pytest

ZERO = "0x0000000000000000000000000000000000000000"


def _hex(a) -> str:
    if isinstance(a, bytes):
        return "0x" + a.hex()
    if hasattr(a, "as_hex"):
        return a.as_hex
    return str(a)


@pytest.fixture
def vault(direct_vm, direct_deploy, direct_owner):
    direct_vm.sender = direct_owner
    return direct_deploy("contracts/halt_vault.py", ZERO)


@pytest.fixture
def agent_setup(vault, direct_vm, direct_owner, direct_alice):
    direct_vm.sender = direct_owner
    vault.register_agent(_hex(direct_alice), 50, 200, 10, "")
    vault.fund_agent(_hex(direct_alice), 1000)
    return vault


def test_register_and_policy(vault, direct_vm, direct_owner, direct_alice, direct_bob):
    direct_vm.sender = direct_owner
    vault.register_agent(_hex(direct_alice), 50, 200, 10, "")
    policy = json.loads(vault.get_policy(_hex(direct_alice)))
    assert policy["registered"] is True
    assert policy["max_per_tx"] == "50"
    assert policy["frozen"] is False
    assert policy["balance"] == "0"

    with direct_vm.expect_revert("already registered"):
        vault.register_agent(_hex(direct_alice), 50, 200, 10, "")
    with direct_vm.expect_revert("positive"):
        vault.register_agent(_hex(direct_bob), 0, 200, 10, "")
    with direct_vm.expect_revert("JSON array"):
        vault.register_agent(_hex(direct_bob), 50, 200, 10, "not-json")

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only owner"):
        vault.register_agent(_hex(direct_bob), 50, 200, 10, "")


def test_spend_happy_path(agent_setup, direct_vm, direct_alice, direct_owner):
    direct_vm.sender = direct_alice
    agent_setup.spend(_hex(direct_owner), 30, "supplies", "paper", "2026-09-12")
    assert agent_setup.get_balance(_hex(direct_alice)) == "970"
    assert agent_setup.get_merchant_credit(_hex(direct_owner)) == "30"
    assert agent_setup.get_tx_count() == "1"
    hist = json.loads(agent_setup.get_tx_history(0, 10))
    assert len(hist) == 1
    assert hist[0]["to"].lower() == _hex(direct_owner).lower()
    assert hist[0]["atto_amount"] == "30"


def test_spend_limits(agent_setup, direct_vm, direct_alice, direct_owner):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("max per-tx"):
        agent_setup.spend(_hex(direct_owner), 51, "supplies", "x", "2026-09-12")
    # daily amount 200: 4x50 ok, 5th exceeds
    for i in range(4):
        agent_setup.spend(_hex(direct_owner), 50, "supplies", f"item{i}", "2026-09-12")
    with direct_vm.expect_revert("daily amount"):
        agent_setup.spend(_hex(direct_owner), 10, "supplies", "over", "2026-09-12")
    # new day resets window
    agent_setup.spend(_hex(direct_owner), 10, "supplies", "next", "2026-09-13")
    status = json.loads(agent_setup.get_status(_hex(direct_alice)))
    assert status["day"] == "2026-09-13"


def test_spend_count_limit(direct_vm, direct_deploy, direct_owner, direct_alice):
    direct_vm.sender = direct_owner
    v = direct_deploy("contracts/halt_vault.py", ZERO)
    v.register_agent(_hex(direct_alice), 1000, 100000, 2, "")
    v.fund_agent(_hex(direct_alice), 100000)
    direct_vm.sender = direct_alice
    v.spend(_hex(direct_owner), 10, "s", "a", "2026-09-12")
    v.spend(_hex(direct_owner), 10, "s", "b", "2026-09-12")
    with direct_vm.expect_revert("daily tx count"):
        v.spend(_hex(direct_owner), 10, "s", "c", "2026-09-12")


def test_allowlist(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    direct_vm.sender = direct_owner
    v = direct_deploy("contracts/halt_vault.py", ZERO)
    v.register_agent(_hex(direct_alice), 1000, 100000, 100, json.dumps([_hex(direct_bob)]))
    v.fund_agent(_hex(direct_alice), 100000)
    direct_vm.sender = direct_alice
    v.spend(_hex(direct_bob), 10, "s", "ok", "2026-09-12")
    with direct_vm.expect_revert("allowlisted"):
        v.spend(_hex(direct_owner), 10, "s", "blocked", "2026-09-12")


def test_freeze_blocks_spend(agent_setup, direct_vm, direct_alice, direct_owner):
    # Only the guardian (zero address here) may flip the flag.
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Only guardian"):
        agent_setup.set_frozen(_hex(direct_alice), True)
    # Prank as the zero guardian to set the flag, then spends revert.
    direct_vm.sender = b"\x00" * 20
    agent_setup.set_frozen(_hex(direct_alice), True)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("frozen"):
        agent_setup.spend(_hex(direct_owner), 10, "s", "x", "2026-09-12")


def test_spend_validation(agent_setup, direct_vm, direct_alice, direct_bob, direct_owner):
    direct_vm.sender = direct_bob  # unknown agent
    with direct_vm.expect_revert("Unknown agent"):
        agent_setup.spend(_hex(direct_owner), 10, "s", "x", "2026-09-12")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("day_key"):
        agent_setup.spend(_hex(direct_owner), 10, "s", "x", "tomorrow")
    with direct_vm.expect_revert("positive"):
        agent_setup.spend(_hex(direct_owner), 0, "s", "x", "2026-09-12")
    with direct_vm.expect_revert("Insufficient balance"):
        agent_setup.spend(_hex(direct_owner), 999999, "s", "x", "2026-09-12")
