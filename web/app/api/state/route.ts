import { NextResponse } from "next/server";
import { addrs, read } from "@/lib/genlayer";

export const dynamic = "force-dynamic";

const CACHE_TTL_MS = 60_000;

type CacheState = {
  at: number;
  body: Record<string, unknown> | null;
  inflight: Promise<Record<string, unknown>> | null;
};

const g = globalThis as unknown as { __haltCache?: CacheState };
g.__haltCache ??= { at: 0, body: null, inflight: null };
const cache = g.__haltCache;

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

async function buildState() {
  const { GUARDIAN, VAULT } = addrs();

  // Wave 1: independent reads in parallel.
  const [stats, agentIds, reportIds, blacklist, txCount] = await Promise.all([
    j(GUARDIAN, "get_stats"),
    j(GUARDIAN, "get_agent_ids"),
    j(GUARDIAN, "get_report_ids"),
    j(GUARDIAN, "get_blacklist"),
    j(VAULT, "get_tx_count"),
  ]);

  const ids = (agentIds as string[]) || [];
  const rids = ((reportIds as string[]) || []).slice(-3);

  // Wave 2: details in parallel.
  const [agents, reports, txs] = await Promise.all([
    Promise.all(
      ids.map(async (id) => {
        const agent = (await j(GUARDIAN, "get_agent", [id])) as { agent_addr: string };
        const policy = await j(VAULT, "get_policy", [agent.agent_addr]);
        return { ...agent, policy };
      }),
    ),
    Promise.all(rids.map((id) => j(GUARDIAN, "get_report", [id]))),
    (async () => {
      const total = parseInt(txCount as string, 10);
      if (!total) return [];
      return j(VAULT, "get_tx_history", [Math.max(0, total - 30), 30]);
    })(),
  ]);

  const statsObj = stats as { pool?: string };
  return {
    ok: true,
    network: "studionet",
    guardian: GUARDIAN,
    vault: VAULT,
    updatedAt: new Date().toISOString(),
    stats,
    pool: statsObj?.pool ?? "0",
    agents,
    reports: (reports as unknown[]).reverse(),
    blacklist,
    txs: (txs as unknown[]).reverse(),
  };
}

function state(): Promise<Record<string, unknown>> {
  if (cache.body && Date.now() - cache.at < CACHE_TTL_MS) {
    return Promise.resolve(cache.body);
  }
  if (!cache.inflight) {
    cache.inflight = buildState()
      .then((body) => {
        cache.body = body;
        cache.at = Date.now();
        return body;
      })
      .finally(() => {
        cache.inflight = null;
      });
  }
  return cache.inflight;
}

// Warm the cache at module load so the first visitor gets an instant page.
state().catch(() => {});

export async function GET() {
  try {
    const body = await state();
    const mode =
      cache.body && Date.now() - cache.at < CACHE_TTL_MS - 1000 ? "cached" : "fresh";
    return NextResponse.json(body, { headers: { "x-halt-cache": mode } });
  } catch (e) {
    if (cache.body) {
      return NextResponse.json(cache.body, { headers: { "x-halt-cache": "stale" } });
    }
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
