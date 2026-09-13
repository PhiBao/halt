"""HALT demo setup: wire and fund a fresh deployment, verifying every step.

Usage:
  HALT_KEYSTORE_PASSWORD=... HALT_GUARDIAN=0x... HALT_VAULT=0x... \\
    python demo/run_demo.py --agent-key agent2 --agent-id halty
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.halt import load_account, make_client, read, wait_for_state, write

CONSTITUTION = (
    "Only buy office supplies from approved vendors. "
    "Never send funds to unknown addresses. "
    "Purchases must be for genuine business needs."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-key", default="agent2")
    ap.add_argument("--agent-id", default="halty")
    ap.add_argument("--allowlist", default="",
                    help="comma-separated vendor addresses, or empty for open")
    ap.add_argument("--guardian", default=os.environ.get("HALT_GUARDIAN", ""))
    ap.add_argument("--vault", default=os.environ.get("HALT_VAULT", ""))
    args = ap.parse_args()
    G, V = args.guardian, args.vault

    owner = load_account("owner")
    agent = load_account(args.agent_key)
    watchdog = load_account("watchdog")
    c_owner, c_agent, c_wd = make_client(owner), make_client(agent), make_client(watchdog)
    A, W, M = agent.address, watchdog.address, owner.address

    print(f"guardian={G}\nvault={V}\nagent={A} ({args.agent_id})\nwatchdog={W}", flush=True)

    print("== wire ==", flush=True)
    write(c_owner, G, "set_vault", args=[V], account=owner)
    wait_for_state("vault link", lambda: read(c_owner, G, "get_vault"), V.lower()[2:8])

    print("== economics ==", flush=True)
    write(c_owner, G, "mint_credits", args=[A, 2000], account=owner)
    write(c_owner, G, "mint_credits", args=[W, 50], account=owner)
    write(c_owner, G, "mint_credits", args=[M, 1000], account=owner)
    write(c_owner, G, "fund_pool", args=[100], account=owner)
    wait_for_state("pool", lambda: read(c_owner, G, "get_pool"), "100")

    print("== vault policy (open allowlist, 500/tx, 2000/day) ==", flush=True)
    allow = "[" + ",".join(f'"{a.strip()}"' for a in args.allowlist.split(",") if a.strip()) + "]" if args.allowlist else "[]"
    print(f"allowlist={allow}", flush=True)
    write(c_owner, V, "register_agent", args=[A, 500, 2000, 100, allow], account=owner)
    write(c_owner, V, "fund_agent", args=[A, 2000], account=owner)
    wait_for_state("policy", lambda: read(c_owner, V, "get_policy", args=[A]), '"registered": true')

    print("== registry ==", flush=True)
    write(c_agent, G, "register_agent", args=[args.agent_id, A, CONSTITUTION], account=agent)
    write(c_wd, G, "register_watchdog", account=watchdog)
    wait_for_state("watchdog", lambda: read(c_owner, G, "get_stake", args=[W]), "10")

    stats = read(c_owner, G, "get_stats")
    print(f"READY: {stats}", flush=True)


if __name__ == "__main__":
    main()
