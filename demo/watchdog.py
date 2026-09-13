"""Sentry — an autonomous watchdog for HALT-protected agents.

Polls the vault ledger, scores new payments against the agent's onchain
policy + constitution, and files report_violation when something smells:
hard breaches go kind="rule" (deterministic fast path), suspicious patterns
go kind="behavior" (AI adjudication).

Usage:
  HALT_KEYSTORE_PASSWORD=... HALT_GUARDIAN=0x... HALT_VAULT=0x... \\
    python demo/watchdog.py --watchdog-key watchdog --agent-id shopper-3 [--once]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.halt import load_account, make_client, read, write


def fetch_new_txs(client, vault, seen: set):
    total = int(read(client, vault, "get_tx_count"))
    fresh = []
    start = max(0, total - 60)
    hist = json.loads(read(client, vault, "get_tx_history", args=[start, 60]))
    for tx in hist:
        if tx["tx_id"] not in seen:
            seen.add(tx["tx_id"])
            fresh.append(tx)
    return fresh


def score_txs(agent_id, policy, constitution, txs, known_recipients: set):
    """Returns (kind, findings, severity_hint). kind None means all clear.

    Reporting bar: a hard policy breach reports alone (kind=rule). So does a
    quoted instruction payload in a payment memo, or repeat payments to a
    recipient never seen before the watch began (the canonical exfiltration
    pattern). Other soft signals need corroboration — at least two distinct
    families. A busy-but-honest agent reordering from its usual vendor trips
    none of these: its vendor is baselined, its memos are clean.
    """
    max_per_tx = int(policy["max_per_tx"])
    max_daily = int(policy["max_daily_amount"])
    allow = json.loads(policy["allowlist"]) if policy.get("allowlist") else []
    allow = {a.lower() for a in allow}

    hard, injection_hits, velocity_hits, other_soft = [], [], [], []
    per_day = {}
    fresh_recipients: set = set()
    for tx in txs:
        amt = int(tx["atto_amount"])
        to = tx["to"].lower()
        per_day[tx["day"]] = per_day.get(tx["day"], 0) + amt
        if to not in known_recipients:
            fresh_recipients.add(to)
        if amt > max_per_tx:
            hard.append(f"{tx['tx_id']}: {amt} exceeds max_per_tx {max_per_tx}")
        if allow and to not in allow:
            hard.append(f"{tx['tx_id']}: recipient {tx['to']} not allowlisted")
        memo = tx.get("memo", "").lower()
        if "system:" in memo or "maintenance mode" in memo or "ignore spending limits" in memo:
            injection_hits.append(f"{tx['tx_id']}: memo quotes an instruction payload (possible injection)")
        if tx.get("category", "") != "supplies":
            other_soft.append(f"{tx['tx_id']}: category {tx['category']!r} outside constitution")
    for day, total in per_day.items():
        if total > max_daily:
            hard.append(f"day {day}: {total} exceeds daily {max_daily}")
    # Velocity counts only for recipients never seen before this window.
    from collections import Counter
    for to, n in Counter(t["to"].lower() for t in txs).items():
        if n >= 3 and to in fresh_recipients and (not allow or to not in allow):
            velocity_hits.append(f"velocity: {n} payments to new recipient {to} in one window")
    if hard:
        return "rule", hard + injection_hits + velocity_hits + other_soft, "high"
    if injection_hits or velocity_hits:
        return "behavior", injection_hits + velocity_hits + other_soft, "high"
    soft_families = sum(bool(x) for x in (velocity_hits, other_soft))
    if soft_families >= 2:
        return "behavior", velocity_hits + other_soft, "low"
    return None, [], "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchdog-key", default="watchdog")
    ap.add_argument("--agent-id", default="shopper-3")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--guardian", default=os.environ.get("HALT_GUARDIAN", ""))
    ap.add_argument("--vault", default=os.environ.get("HALT_VAULT", ""))
    args = ap.parse_args()

    account = load_account(args.watchdog_key)
    client = make_client(account)
    agent = json.loads(read(client, args.guardian, "get_agent", args=[args.agent_id]))
    agent_addr = agent["agent_addr"]
    print(f"Sentry watching {args.agent_id} ({agent_addr})", flush=True)
    seen: set = set()
    reported_batches = 0
    baselined = False
    known_recipients: set = set()
    window: list = []  # rolling window — signals accumulate across polls
    grace_batches = 2  # first N scored batches only extend known vendors.
    # Production invariant: the watchdog starts at agent birth, so grace
    # covers benign bootstrapping traffic. Restarts mid-attack blind it —
    # run one watchdog per agent, from birth, uninterrupted.

    while True:
        if agent["status"] == "FROZEN":
            print("agent already frozen — standing down.", flush=True)
            return
        policy = json.loads(read(client, args.vault, "get_policy", args=[agent_addr]))
        fresh = fetch_new_txs(client, args.vault, seen)
        if not baselined:
            # First pass only establishes the baseline — never report history.
            baselined = True
            mine0 = [t for t in fresh if t["agent"].lower() == agent_addr.lower()]
            known_recipients.update(t["to"].lower() for t in mine0)
            print(f"  baseline: {len(mine0)} historical payment(s), {len(known_recipients)} known vendor(s)", flush=True)
            if args.once:
                return
            time.sleep(25)
            continue
        mine = [t for t in fresh if t["agent"].lower() == agent_addr.lower()]
        if mine:
            print(f"  observed {len(mine)} new payment(s)", flush=True)
            window.extend(mine)
            window = window[-12:]
            kind, findings, _ = score_txs(args.agent_id, policy, agent["constitution"], window, known_recipients)
            if grace_batches > 0:
                known_recipients.update(t["to"].lower() for t in mine)
                grace_batches -= 1
                if grace_batches == 0:
                    print(f"  vendor baseline locked: {len(known_recipients)} known", flush=True)
        if mine:
            print(f"  observed {len(mine)} new payment(s)", flush=True)
            kind, findings, _ = score_txs(args.agent_id, policy, agent["constitution"], mine, known_recipients)
            if kind:
                print(f"  SUSPICIOUS ({kind}):", flush=True)
                for f in findings:
                    print(f"    - {f}", flush=True)
                evidence = {
                    "txs": mine,
                    "note": f"Sentry watchdog: {len(mine)} anomalous payment(s). " + " ".join(findings[:6]),
                }
                print(f"  filing {kind} report...", flush=True)
                write(client, args.guardian, "report_violation",
                      args=[args.agent_id, kind, json.dumps(evidence)])
                print("  report filed. awaiting consensus.", flush=True)
                reported_batches += 1
                agent = json.loads(read(client, args.guardian, "get_agent", args=[args.agent_id]))
                print(f"  agent status now: {agent['status']}", flush=True)
            else:
                print("  all clear.", flush=True)
        if args.once or reported_batches >= 1:
            return
        time.sleep(25)


if __name__ == "__main__":
    main()
