"""Shared GenLayer client helpers for the HALT demo scripts.

Keys never live in the repo: scripts decrypt the CLI keystores in
~/.genlayer/keystores/ with HALT_KEYSTORE_PASSWORD from the environment.
"""
import json
import os
import time
from pathlib import Path

from eth_account import Account

from genlayer_py.chains import studionet
from genlayer_py.client import create_client
from genlayer_py.types import TransactionStatus

KEYSTORE_DIR = Path.home() / ".genlayer" / "keystores"


def load_account(name: str):
    password = os.environ.get("HALT_KEYSTORE_PASSWORD")
    if not password:
        raise RuntimeError("Set HALT_KEYSTORE_PASSWORD env var")
    with open(KEYSTORE_DIR / f"{name}.json") as f:
        keystore = json.load(f)
    return Account.from_key(Account.decrypt(keystore, password))


def make_client(account):
    return create_client(chain=studionet, account=account)


def read(client, address, method, args=None):
    return client.read_contract(address=address, function_name=method, args=args or [])


def write(client, address, method, args=None, account=None, timeout_s=1500):
    tx_hash = client.write_contract(
        address=address, function_name=method, args=args or [], account=account
    )
    print(f"    tx {tx_hash.hex() if hasattr(tx_hash, 'hex') else tx_hash}", flush=True)
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hash, status=TransactionStatus.ACCEPTED,
        interval=8000, retries=max(10, timeout_s // 8),
    )
    ok, payload = execution_outcome(receipt)
    if not ok:
        raise RuntimeError(f"{method} failed: {payload}")
    return receipt


def execution_outcome(receipt):
    """ACCEPTED/FINALIZED is not success — inspect the leader receipt."""
    try:
        data = receipt["consensus_data"] if isinstance(receipt, dict) else receipt.consensus_data
        leaders = data["leader_receipt"] if isinstance(data, dict) else data.leader_receipt
        leader = (leaders or [None])[0]
        if leader is None:
            return False, "no leader receipt"
        get = (lambda k, d=None: leader.get(k, d)) if isinstance(leader, dict) else (lambda k, d=None: getattr(leader, k, d))
        if get("execution_result") == "SUCCESS":
            res = get("result") or {}
            payload = res.get("payload", "ok") if isinstance(res, dict) else getattr(res, "payload", "ok")
            return True, payload
        res = get("result") or {}
        payload = res.get("payload") if isinstance(res, dict) else getattr(res, "payload", None)
        return False, payload or get("execution_result", "unknown")
    except Exception as e:  # noqa: BLE001
        return False, f"receipt parse error: {e}"


def wait_for_state(desc, fn, expect_substr, timeout_s=420, interval_s=8):
    """Poll a read call until its output contains expect_substr."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            out = fn()
            text = out if isinstance(out, str) else json.dumps(out)
            if expect_substr.lower() in text.lower():
                return out
        except Exception:
            pass
        time.sleep(interval_s)
    raise TimeoutError(f"Timed out waiting for: {desc}")
