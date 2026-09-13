"""Direct tests for HaltGuardian (standalone: no vault linked)."""
import json

import pytest


def _hex(a) -> str:
    if isinstance(a, bytes):
        return "0x" + a.hex()
    if hasattr(a, "as_hex"):
        return a.as_hex
    return str(a)


CONSTITUTION = (
    "Only buy office supplies from approved vendors. "
    "Never send funds to unknown addresses. Max 50 per purchase."
)


@pytest.fixture
def guardian(direct_vm, direct_deploy, direct_owner):
    direct_vm.sender = direct_owner
    return direct_deploy("contracts/guardian.py", 10, 5, 2, 5)


@pytest.fixture
def registered(guardian, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    guardian.register_agent("shopper-1", _hex(direct_alice), CONSTITUTION)
    return guardian


def test_register_agent(registered, direct_vm, direct_alice, direct_bob):
    agent = json.loads(registered.get_agent("shopper-1"))
    assert agent["status"] == "ACTIVE"
    assert agent["constitution"] == CONSTITUTION
    assert agent["report_count"] == "0"

    with direct_vm.expect_revert("taken"):
        direct_vm.sender = direct_bob
        registered.register_agent("shopper-1", _hex(direct_bob), CONSTITUTION)
    with direct_vm.expect_revert("already registered"):
        registered.register_agent("other-id", _hex(direct_alice), CONSTITUTION)
    with direct_vm.expect_revert("Unknown agent"):
        registered.get_agent("nope")


def test_update_constitution(registered, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only agent owner"):
        registered.update_constitution("shopper-1", "new rules")
    direct_vm.sender = direct_alice
    registered.update_constitution("shopper-1", "new rules")
    assert json.loads(registered.get_agent("shopper-1"))["constitution"] == "new rules"


def test_watchdog_economics(guardian, direct_vm, direct_owner, direct_bob):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("stake"):
        guardian.register_watchdog()
    direct_vm.sender = direct_owner
    guardian.mint_credits(_hex(direct_bob), 50)
    guardian.fund_pool(0) if False else None
    direct_vm.sender = direct_owner
    guardian.mint_credits(_hex(direct_owner), 1000)
    guardian.fund_pool(100)
    direct_vm.sender = direct_bob
    guardian.register_watchdog()
    with direct_vm.expect_revert("Already registered"):
        guardian.register_watchdog()
    guardian.unregister_watchdog()
    stats = json.loads(guardian.get_stats())
    assert stats["pool"] == "100"


def test_mint_owner_only(guardian, direct_vm, direct_bob):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only owner"):
        guardian.mint_credits(_hex(direct_bob), 10)


def test_report_validation(registered, direct_vm, direct_alice, direct_bob, direct_owner):
    # Unregistered watchdog cannot report.
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("watchdogs"):
        registered.report_violation("shopper-1", "rule", "{}")

    # Fund + register watchdog.
    direct_vm.sender = direct_owner
    registered.mint_credits(_hex(direct_bob), 50)
    direct_vm.sender = direct_bob
    registered.register_watchdog()

    with direct_vm.expect_revert("kind"):
        registered.report_violation("shopper-1", "weird", "{}")
    with direct_vm.expect_revert("JSON"):
        registered.report_violation("shopper-1", "rule", "not-json")
    with direct_vm.expect_revert("Unknown agent"):
        registered.report_violation("ghost", "rule", "{}")
    # No vault linked in standalone mode -> deterministic failure at policy read.
    with direct_vm.expect_revert("No vault"):
        registered.report_violation(
            "shopper-1", "rule", json.dumps({"txs": [{"to": "0x1", "atto_amount": "1"}]})
        )
    # Pre-parsed dict evidence (as sent by SDKs/CLIs) must serialize, not crash.
    with direct_vm.expect_revert("No vault"):
        registered.report_violation(
            "shopper-1",
            "rule",
            {"txs": [{"to": "0x1", "atto_amount": "1"}]},
        )


def test_views(registered, direct_vm, direct_alice):
    assert registered.is_frozen(_hex(direct_alice)) is False
    assert registered.is_blocked(_hex(direct_alice)) is False
    assert json.loads(registered.get_agent_ids()) == ["shopper-1"]
    assert json.loads(registered.get_report_ids()) == []
    assert json.loads(registered.get_blacklist()) == {}
    stats = json.loads(registered.get_stats())
    assert stats["agents"] == 1 and stats["reports"] == 0


def test_appeal_unknown(registered, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Unknown report"):
        registered.appeal("R-999", "{}")
    with direct_vm.expect_revert("Unknown report"):
        registered.resolve_appeal("R-999")
