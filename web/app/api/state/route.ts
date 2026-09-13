import { NextResponse } from "next/server";
import { addrs, read } from "@/lib/genlayer";

export const dynamic = "force-dynamic";

async function j(address: string, fn: string, args: unknown[] = []) {
  const raw = await read(address, fn, args);
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  }
  return raw;
}

export async function GET() {
  try {
    const { GUARDIAN, VAULT } = addrs();
    const [stats, pool, agentIds, reportIds, blacklist, txCount] = await Promise.all([
      j(GUARDIAN, "get_stats"),
      j(GUARDIAN, "get_pool"),
      j(GUARDIAN, "get_agent_ids"),
      j(GUARDIAN, "get_report_ids"),
      j(GUARDIAN, "get_blacklist"),
      j(VAULT, "get_tx_count"),
    ]);

    const agents = [];
    for (const id of agentIds as string[]) {
      const agent = await j(GUARDIAN, "get_agent", [id]);
      const policy = await j(VAULT, "get_policy", [(agent as { agent_addr: string }).agent_addr]);
      agents.push({ ...(agent as object), policy });
    }

    const reports = [];
    for (const id of (reportIds as string[]).slice(-10)) {
      reports.push(await j(GUARDIAN, "get_report", [id]));
    }

    const total = parseInt(txCount as string, 10);
    const txs = total > 0 ? await j(VAULT, "get_tx_history", [Math.max(0, total - 30), 30]) : [];

    return NextResponse.json({
      ok: true,
      network: "studionet",
      guardian: GUARDIAN,
      vault: VAULT,
      updatedAt: new Date().toISOString(),
      stats,
      pool,
      agents,
      reports: (reports as unknown[]).reverse(),
      blacklist,
      txs: (txs as unknown[]).reverse(),
    });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
