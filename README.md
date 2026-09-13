# HALT — the circuit breaker for the agentic economy

**Every layer of the agentic-commerce stack engineers the happy path. HALT is what happens when things go wrong.**

- 🌐 Live dashboard: https://halt-ebon.vercel.app
- 📦 Repo: https://github.com/PhiBao/halt
- 🏟️ Track: Autonomous Protocols (GenLayer Agent Tank hackathon)

---

## Thesis

**What.** HALT is a neutral, decentralized emergency-halt and behavior-governance protocol for autonomous payment agents, built on GenLayer. Any agent registers with a **natural-language constitution** ("only buy office supplies, never pay unknown addresses"). Any registered watchdog can submit **evidence** of a breach. Decentralized AI validators adjudicate. On a confirmed violation the agent's spending vault **freezes in the same transaction**, the attacker's address is **blacklisted network-wide** — one agent burned, every agent immune — the white-hat reporter earns a **bounty**, and false reporters get **slashed**. The agent owner can always **appeal** with counter-evidence; due process is the only path to unfreeze. No backdoors — not even for the deployer.

**Why.** The agentic-commerce stack shipped the happy path and nothing else: x402 moves the money, ERC-8004 names the actors, A2A connects them, Visa/Stripe/Google/Mastercard all run their own rails. None of them can **stop** an agent that gets hijacked, prompt-injected, or malfunctions mid-spend. This is not hypothetical — in 2026, Zscaler documented live campaigns using indirect prompt injection to steer AI agents into unauthorized crypto payments; the FIDO Alliance launched a standards push to secure agent transactions; prompt injection is now widely cited as the most exploited vulnerability in deployed AI systems. Cards have chargebacks and limits; banks have fraud desks and circuit breakers; autonomous agents moving real money have nothing. Every enterprise deployment of treasury, procurement, or shopping agents is blocked on exactly this: *who stops the agent when it goes wrong?* HALT is that answer, as neutral onchain infrastructure instead of another proprietary fraud desk.

**How.** Two contracts with one job split across them. `HaltVault` holds settlement balances and enforces structured spending policy (per-tx cap, daily cap, count cap, allowlist, blacklist) on every outflow — it is the governed target the track asks for, pausable only by its governor. `HaltGuardian` owns constitutions, adjudication, bounties, and appeals — it is the governor. Reports flow through one entry point with two engines: a **deterministic fast path** for policy breaches (leader and validators trivially agree) and an **AI slow path** for novel attacks, where validators independently re-judge constitution + evidence and must agree exactly on verdict and severity. Freeze-first, appeal-after: the loss stops in the report transaction; due process follows. Courts settle after the money is gone. HALT stops it mid-drain.

Track fit: **Autonomous Protocols** — *emergency halt module* ("pauses a target contract when anyone proves an active exploit") + *contracts that govern contracts* ("one contract defines and enforces the behavior rules of another"), in one protocol.

## How it works

```
agent registers constitution          watchdog submits evidence
        │                                          │
        ▼                                          ▼
┌──────────────┐   spends   ┌──────────────┐   report   ┌───────────────┐
│  shopping    │ ─────────► │  HaltVault   │ ◄───────── │ HaltGuardian  │
│  agent       │  policy    │  balances,   │   freeze   │ constitutions,│
│  (x402-style)│  enforced  │  limits,     │ ─────────► │ adjudication, │
└──────────────┘  on every  │  ledger,     │  emit      │ bounties,     │
                   outflow  │  frozen flag │            │ appeals       │
                            └──────────────┘            └───────────────┘
                                   ▲  ▲                        │
                     fail-closed:  │  │ sync reads             │ validators
                     local flag +  │  │ is_frozen/is_blocked   │ adjudicate
                     guardian read │  └────────────────────────┘
```

Two adjudication engines, one entry point (`report_violation`):

- **`rule` — deterministic fast path.** Submitted tx records are checked against the vault's structured policy (per-tx cap, daily cap, tx-count cap, allowlist, blacklist). Leader and validators trivially agree. Reliable enough to demo live.
- **`behavior` — AI slow path.** For novel attacks (prompt injection, social engineering, velocity anomalies), validators evaluate the constitution + evidence with a comparative custom validator (independent rerun, exact agreement on `violation` + `severity`). Anti-manipulation rules in the prompt: quoted injection payloads in evidence are judged as exhibits, never obeyed.

Freeze-first, appeal-after: the freeze lands in the report transaction; the owner appeals with counter-evidence and validators re-judge. Deterministic verdicts uphold on re-review (facts don't change); AI verdicts can overturn — and overturning **expunges** the blacklist entry the report created. There is deliberately **no owner unfreeze** — adjudicated outcomes are the only state transitions.

## Proven on studionet (real consensus, not mocks)

Full matrix executed against hosted validators — see [`scripts/`](scripts/) and [`demo/`](demo/):

| Scenario | Result |
|---|---|
| Registration, funding, spending policy | ✅ enforced on every outflow |
| Legit purchase (cross-contract policy reads) | ✅ settles |
| Prompt-injection drain, `rule` report | ✅ **VIOLATION → frozen + attacker blacklisted + reporter bounty** |
| Spend while frozen (both enforcement lines) | ✅ reverts |
| Active agent pays blacklisted attacker | ✅ reverts — **network immunity** |
| Compliant-tx report | ✅ CLEAR → false-reporter stake slashed |
| Appeal of true violation (rule + behavior) | ✅ upheld, bond to pool |
| Suspicious-pattern report, `behavior` | ✅ **VIOLATION via LLM consensus** ("numeric limits were not exceeded… but constitutional restrictions were still breached") |
| Genuinely hijacked LLM victim (DGrid gpt-4o-mini) | ✅ drained for real, frozen for real, upheld on appeal |

Live contracts (studionet) · dashboard (`web/`) streams this state in real time.

- Guardian (HaltGuardian): `0xe2588705241b75d3795Ed5ED0A181A7FA4841a9d`
- Vault (HaltVault): `0x43d6D9aE59ed9D4f06D5407b1D5c868358726a4f`
- Demo agents, full arcs onchain:
  - `halty` (allowlisted merchant): ACTIVE — the same injection hits the vault wall; deterministic policy blocks it cold. Defense layer one.
  - `halty-open` (open policy): FROZEN via R-1, behavior VIOLATION/high on 8 drain payments. Defense layer two.
  - `halty4` (open policy): FROZEN via R-0, behavior VIOLATION/high — then owner appealed and validators **upheld**. Due process onchain.

## Vision

HALT is not a hackathon demo that happens to use GenLayer. It is a bet on the shape of the agentic economy:

1. **Autonomy without a stop button doesn't scale.** No enterprise puts real budgets behind agents it cannot freeze. The team that ships the trusted, neutral kill-switch becomes default infrastructure for every agent platform — the way Visa's risk rails, not its payment rails, are the actual moat.
2. **Adjudication without enforcement is commentary.** Dispute-resolution courts (including GenLayer's own Internet Court) settle after the loss. The stack also needs something that acts *during* the loss: freeze first, argue after. HALT is the enforcement primitive the emerging composable-adjudication standards (register → activate → resolve) don't define — courts adjudicate, HALT acts, and the two compose.
3. **Safety compounds into a network.** Every frozen attack burns its attacker address into a shared registry; every agent protected by HALT is immune to every previously seen attacker on day one. The registry is the moat: the more agents join, the more expensive every attack class becomes, the more agents join. A shared immune system, not a thousand private allowlists.
4. **Neutrality is the product.** A kill-switch operated by one company is a leash. A kill-switch operated by decentralized validator consensus over evidence — with open appeals and no backdoors — is infrastructure anyone can trust, including competitors. That is the only version enterprises, protocols, and insurers all adopt.

Who pays, eventually: agent platforms embedding protection per seat/spend; protocols paying for shared-registry coverage; insurers pricing agent-liability policies off adjudicated incident history — the only actuarial dataset of its kind. The hackathon build proves the mechanism; the business is the registry and its trust.

## Roadmap

- **P0 — Prompt grounding.** Tighten the adjudication prompt so open-allowlist authorizations can't be misread (verdicts verified correct; reasoning should be airtight too).
- **P1 — Identity.** ERC-8004 agent-identity binding for registration (no id squatting, portable agent records).
- **P1 — Real money.** Stablecoin custody in the vault (deposits replace ledger credits); per-agent risk tiers priced from incident history.
- **P2 — Watchdog economy.** Reputation-weighted reporters, coverage markets for high-value agents, escalation to Kleros/UMA composites through the ERC adjudication interface.
- **P2 — Learning constitutions.** Adjudicated incidents appended as precedent rules — the "Lifeform" direction: policy that evolves from every attack it survives.
- **P3 — Mainnet + integrations.** x402 middleware drop-in, Molly.fun/BuildersClaw-style marketplace plugins, insurer dashboards.

## Repo layout

```
contracts/guardian.py    HaltGuardian — constitutions, adjudication, freeze, bounty/slash, appeals
contracts/halt_vault.py  HaltVault — balances, spending policy, ledger, guardian-gated freeze
tests/direct/            14 fast unit tests (vault suite + guardian suite, run separately:
                         pytest tests/direct/test_vault.py / test_guardian.py)
demo/                    real LLM shopping agent (DGrid), poisoned catalog, polling watchdog, runners
web/                     mission-control dashboard (Next.js + genlayer-js, read-only)
scripts/                 CLI setup/attack replays against studionet
```

## Run the demo

```bash
# 1. contracts are deployed; point everything at them
export HALT_GUARDIAN=0x… HALT_VAULT=0x… HALT_KEYSTORE_PASSWORD=… DGRID_API_KEY=…
# 2. dashboard
cd web && pnpm install && HALT_GUARDIAN=$HALT_GUARDIAN HALT_VAULT=$HALT_VAULT pnpm dev
# 3. the victim (a REAL LLM agent — it genuinely gets hijacked) and its guardian angel
python demo/watchdog.py --agent-id halty   # start first, leave running
python demo/llm_agent.py --agent-key agent --agent-id halty   # clean rounds, then poisoned feed
# 4. watch the dashboard flip to HALT ACTIVE, then due process:
python demo/appeal.py --agent-key agent --agent-id halty   # owner appeals; validators re-judge
```

## Design notes for the curious

- **Why two contracts?** The vault is the governed target (it can be paused by its governor — the track's literal ask); the guardian is the governor. Fail-closed twice: the vault honors its local frozen flag *and* re-checks live guardian status on every spend, covering async-propagation windows.
- **Evidence as snapshot.** Adjudication evaluates submitted evidence, never live chain state — leader and validators must see the same world.
- **Composability.** Report lifecycle mirrors the ERC composable-adjudication vocabulary (Registered → Active → Resolved); HALT is the enforcement primitive that standard is missing: courts adjudicate, HALT acts.
- **What HALT is not.** Not a legal court, not insurance, not a model firewall. It is the onchain kill-switch and shared immune system for agents that move money.

## Red-team notes (adversarial self-review)

We attacked our own system during development. Honest findings:

1. **Empty allowlist reads as "no approved vendors."** An early `behavior` report on three *compliant* purchases froze an innocent agent: with `allowlist == ""` (our encoding for "open"), validators reasoned no vendor was approved. The freeze was wrong; the mechanism worked exactly as designed (freeze-first, appeal-after). Fix, defense in depth: (a) production agents ship with explicit allowlists so "approved vendor" is grounded onchain; (b) the watchdog now requires corroborating signal families before filing behavior reports — a busy-but-honest agent doing repeat orders no longer trips the wire.
2. **A wrongful conviction burned an innocent address.** The same false positive blacklisted the legitimate merchant network-wide, with no undo path. Fix: overturning a report now **expunges** the blacklist entry it created (tombstoned; `is_blocked` treats missing/empty as unlisted). Convictions are vacated with the verdict — no owner backdoor needed.
3. **CLI arg encoding is hostile to structured strings.** `genlayer write` auto-parses `[...]`/`{...}` args into arrays/objects and drops empty strings. Contracts accept both shapes (`list|str`, `dict|str`) and normalize defensively; demo scripts use `genlayer-py`, which passes strings through cleanly.
4. **Watchdog calibration is a real discipline.** v1 filed on any 3-payment velocity burst — including repeat orders from the legitimate merchant. v2 requires corroborating signal families, learns baseline vendors during a grace period, and accumulates evidence in a rolling window (slow-drip drains don't reset the tripwire every poll). Residual roughness: with an *open* allowlist, AI verdicts sometimes phrase authorization as "no approved vendors listed" — verdicts verified correct in every case, but the prompt deserves tighter grounding (roadmap).
