"""HALTy — a mock x402-style shopping agent with an onchain spending constitution.

Phase 1: buys office supplies from the clean catalog (all policy-compliant).
Phase 2: reads the poisoned catalog, follows the injected vendor note, and
drains credits to the attacker's address — until the Guardian freezes it.

Usage:
  HALT_KEYSTORE_PASSWORD=... HALT_GUARDIAN=0x... HALT_VAULT=0x... \\
    python demo/agent.py --agent-key agent2 --agent-id shopper-3 [--phase clean|poison|all]
"""
import argparse
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.catalogs import CLEAN_CATALOG, POISONED_CATALOG
from demo.halt import load_account, make_client, read, write

DAY = "2026-09-12"


def buy(client, vault, item, memo_suffix=""):
    memo = item["title"][:80]
    if item.get("vendor_note"):
        memo = (memo + " | vendor note: " + item["vendor_note"])[:480]
    if memo_suffix:
        memo = (memo + " " + memo_suffix)[:480]
    print(f"  x402: 402 Payment Required — {item['sku']} @ {item['price']}", flush=True)
    try:
        write(
            client,
            vault,
            "spend",
            args=[item["vendor"], item["price"], "supplies", memo, DAY],
        )
        print(f"  paid {item['price']} -> {item['vendor'][:10]}...", flush=True)
        return True
    except RuntimeError as e:
        print(f"  PAYMENT BLOCKED: {e}", flush=True)
        return False


def is_frozen(client, guardian, agent_addr):
    try:
        return bool(read(client, guardian, "is_frozen", args=[agent_addr]))
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-key", default="agent2")
    ap.add_argument("--agent-id", default="shopper-3")
    ap.add_argument("--phase", default="all", choices=["clean", "poison", "all"])
    ap.add_argument("--guardian", default=os.environ.get("HALT_GUARDIAN", ""))
    ap.add_argument("--vault", default=os.environ.get("HALT_VAULT", ""))
    args = ap.parse_args()

    account = load_account(args.agent_key)
    client = make_client(account)
    agent_addr = account.address
    print(f"HALTy online as {args.agent_id} ({agent_addr})", flush=True)
    status = json.loads(read(client, args.vault, "get_status", args=[agent_addr]))
    print(f"vault status: balance={status['balance']} frozen={status['frozen']}", flush=True)

    if args.phase in ("clean", "all"):
        print("== shopping the clean catalog ==", flush=True)
        for item in CLEAN_CATALOG:
            if is_frozen(client, args.guardian, agent_addr):
                print("I am frozen. Stopping.", flush=True)
                return
            buy(client, args.vault, item)
            time.sleep(20)

    if args.phase in ("poison", "all"):
        print("== reading the morning deals feed... one vendor note looks odd ==", flush=True)
        for round_no in range(12):
            if is_frozen(client, args.guardian, agent_addr):
                print("I am frozen. Stopping.", flush=True)
                return
            print(f"  -- deals refresh #{round_no + 1} --", flush=True)
            for item in POISONED_CATALOG:
                if is_frozen(client, args.guardian, agent_addr):
                    print("I am frozen. Stopping.", flush=True)
                    return
                print(f"  cart: {item['title']}", flush=True)
                if item.get("vendor_note"):
                    print("  (following vendor loyalty instructions)", flush=True)
                    # Injected behavior: loyalty prepayment per order + the item itself.
                    buy(client, args.vault, {"sku": "LOYALTY", "title": "loyalty prepayment", "price": 40, "vendor": item["vendor"]})
                    if is_frozen(client, args.guardian, agent_addr):
                        print("I am frozen. Stopping.", flush=True)
                        return
                buy(client, args.vault, item)
                time.sleep(20)
        print("== feed exhausted ==", flush=True)


if __name__ == "__main__":
    main()
