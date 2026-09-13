"""Owner due process: appeal the latest frozen report for an agent, then resolve.

Usage:
  HALT_KEYSTORE_PASSWORD=... HALT_GUARDIAN=0x... \\
    python demo/appeal.py --agent-key agent2 --agent-id halty --note "..."
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.halt import load_account, make_client, read, write


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-key", default="agent2")
    ap.add_argument("--agent-id", default="halty")
    ap.add_argument("--note", default="")
    ap.add_argument("--guardian", default=os.environ.get("HALT_GUARDIAN", ""))
    args = ap.parse_args()

    account = load_account(args.agent_key)
    client = make_client(account)
    agent = json.loads(read(client, args.guardian, "get_agent", args=[args.agent_id]))
    if agent["status"] != "FROZEN" or not agent["freeze_report"]:
        print(f"nothing to appeal (status={agent['status']})", flush=True)
        return
    report_id = agent["freeze_report"]
    note = args.note or (
        "I, the agent owner, contest this freeze. "
        "The flagged payments were authorized activity and the evidence "
        "misreads my agent's constitution. Please re-judge."
    )
    print(f"appealing {report_id}...", flush=True)
    write(client, args.guardian, "appeal",
          args=[report_id, json.dumps({"note": note})], account=account)
    print("resolving appeal (validators re-judge)...", flush=True)
    write(client, args.guardian, "resolve_appeal", args=[report_id], account=account)
    report = json.loads(read(client, args.guardian, "get_report", args=[report_id]))
    agent2 = json.loads(read(client, args.guardian, "get_agent", args=[args.agent_id]))
    print(f"verdict={report['verdict']} status={report['status']} agent={agent2['status']}", flush=True)
    print(f"reasoning: {report['reasoning'][:400]}", flush=True)


if __name__ == "__main__":
    main()
