"use client";
import { useEffect, useState } from "react";

type Agent = {
  agent_id: string;
  agent_addr: string;
  owner: string;
  constitution: string;
  status: string;
  frozen_at: string;
  freeze_report: string;
  report_count: string;
  policy: {
    registered: boolean;
    max_per_tx: string;
    max_daily_amount: string;
    max_daily_count: string;
    allowlist: string;
    frozen: boolean;
    balance: string;
  };
};
type Report = {
  report_id: string;
  agent_id: string;
  reporter: string;
  kind: string;
  status: string;
  verdict: string;
  severity: string;
  action: string;
  attacker: string;
  reasoning: string;
  appeal_by: string;
  created_at: string;
  resolved_at: string;
};
type Tx = {
  tx_id: string;
  agent: string;
  to: string;
  atto_amount: string;
  category: string;
  memo: string;
  day: string;
};
type State = {
  ok: boolean;
  network: string;
  guardian: string;
  vault: string;
  updatedAt: string;
  stats: { agents: number; reports: number; frozen_agents: number; pool: string; blacklisted: number };
  pool: string;
  agents: Agent[];
  reports: Report[];
  blacklist: Record<string, string>;
  txs: Tx[];
  error?: string;
};

const short = (a: string) => (a && a.length > 14 ? a.slice(0, 8) + "…" + a.slice(-6) : a);

export default function Page() {
  const [s, setS] = useState<State | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fetch("/api/state", { cache: "no-store" });
        const j = (await r.json()) as State;
        if (alive) setS(j);
      } catch (e) {
        if (alive) setS({ ok: false, error: String(e) } as State);
      }
    };
    load();
    const t = setInterval(load, 60000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  if (!s) return <div className="wrap"><div className="loading">connecting to studionet…</div></div>;
  if (!s.ok) return <div className="wrap"><div className="err">state error: {(s as State).error}</div></div>;

  const halted = s.stats.frozen_agents > 0;
  const blocked = new Set(Object.keys(s.blacklist).map((k) => k.toLowerCase()));

  return (
    <div className="wrap">
      <div className="topbar">
        <img src="/logo.svg" alt="HALT" className="mark" />
        <div className="logo">HALT</div>
        <div className="tag">circuit breaker for the agentic economy · {s.network}</div>
        <span className={`pill ${halted ? "halt" : "ok"}`}>
          {halted ? `⛔ HALT ACTIVE — ${s.stats.frozen_agents} FROZEN` : "● ALL CLEAR"}
        </span>
        <div className="live"><span className="dot" />LIVE · {new Date(s.updatedAt).toLocaleTimeString()}</div>
      </div>
      <div className="addr" style={{ marginBottom: 14 }}>
        guardian {short(s.guardian)} · vault {short(s.vault)}
      </div>

      <div className="grid">
        <div>
          <div className="card">
            <h2>PROTECTED AGENTS</h2>
            {s.agents.map((a) => (
              <div key={a.agent_id} className={`card agent ${a.status === "FROZEN" ? "frozen" : ""}`} style={{ marginBottom: 10 }}>
                <div className="agent-head">
                  <span className="agent-id">{a.agent_id}</span>
                  <span className={`badge ${a.status === "FROZEN" ? "frozen" : "active"}`}>{a.status}</span>
                  {a.freeze_report && <span className="addr">via {a.freeze_report}</span>}
                </div>
                <dl className="kv">
                  <dt>balance</dt><dd>{a.policy?.balance} credits</dd>
                  <dt>limits</dt><dd>{a.policy?.max_per_tx}/tx · {a.policy?.max_daily_amount}/day · {a.policy?.max_daily_count} txs</dd>
                  <dt>allowlist</dt><dd>{a.policy?.allowlist ? short(a.policy.allowlist) : "open"}</dd>
                  <dt>address</dt><dd className="addr">{a.agent_addr}</dd>
                </dl>
                <div className="const">“{a.constitution}”</div>
              </div>
            ))}
          </div>

          <div className="card">
            <h2>ADJUDICATION TIMELINE</h2>
            {s.reports.length === 0 && <div className="tag">no reports yet — the tank is quiet.</div>}
            {s.reports.map((r) => (
              <div key={r.report_id} className={`report ${r.verdict === "VIOLATION" ? "v" : "c"}`}>
                <div>
                  <b>{r.report_id}</b> · {r.agent_id} · <span className="addr">{r.kind}</span>{" "}
                  <span className={`vbadge ${r.verdict}`}>{r.verdict || r.status}</span>{" "}
                  {r.severity !== "none" && <span className={r.severity === "high" ? "sev-high" : "sev-low"}>[{r.severity}]</span>}
                </div>
                {r.attacker && <div className="addr">attacker → {r.attacker}</div>}
                {r.reasoning && <div className="reason">{r.reasoning}</div>}
                {r.appeal_by && <div className="reason">appeal by {short(r.appeal_by)} — {r.status}</div>}
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="card">
            <h2>LIVE PAYMENT FEED</h2>
            <div className="feed">
              {s.txs.length === 0 && <div className="tag">no payments yet.</div>}
              {s.txs.map((t) => {
                const bad = blocked.has(t.to.toLowerCase());
                return (
                  <div key={t.tx_id} className={`tx ${bad ? "bad" : ""}`}>
                    <span className="amt">{t.atto_amount}</span> · {short(t.agent)} →{" "}
                    <span className={bad ? "to-bad" : ""}>{bad ? "☠ " + short(t.to) : short(t.to)}</span>
                    <div className="addr">{t.tx_id} · {t.category} · {t.memo.slice(0, 90)}</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <h2>SHARED IMMUNE SYSTEM</h2>
            {Object.keys(s.blacklist).length === 0 && <div className="tag">no burned addresses.</div>}
            <div className="chips">
              {Object.entries(s.blacklist).map(([addr, rep]) => (
                <span key={addr} className="chip" title={`burned by ${rep}`}>☠ {short(addr)} <span className="addr">({rep})</span></span>
              ))}
            </div>
          </div>

          <div className="card">
            <h2>WATCHDOG ECONOMICS</h2>
            <div className="econ">
              <div><b>{s.pool}</b><span>bounty pool</span></div>
              <div><b>{s.stats.reports}</b><span>reports filed</span></div>
              <div><b>{s.stats.blacklisted}</b><span>burned</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
