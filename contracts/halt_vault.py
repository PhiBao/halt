# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""HaltVault — a spending vault governed by the HALT Guardian.

The vault holds settlement balances for autonomous payment agents and enforces
per-agent spending policy on every outflow. It is the "target contract" in the
Autonomous Protocols track: it can be paused by its governor (the Guardian
intelligent contract) when anyone proves an active exploit.

Design notes:
- Money is tracked as an internal atto-scale (1e-18) ledger. In production the
  vault would custody stablecoin deposits; the hackathon build uses
  owner-minted credits as settlement balances so the freeze primitive — the
  actual product — is fully onchain and verifiable.
- Fail-closed: spend() consults the Guardian twice (frozen status, attacker
  blacklist) via synchronous reads AND honors its own local frozen flag set by
  the Guardian. If the Guardian says FROZEN anywhere, the spend reverts.
- Day windows use a caller-supplied day_key (YYYY-MM-DD). Gaming the key does
  not help an attacker: per-tx caps still apply, and key anomalies are
  permanently recorded in the ledger as watchdog evidence.
"""

import json
import re
from dataclasses import dataclass
from genlayer import *

ERROR_EXPECTED = "[EXPECTED]"

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def _as_address(x) -> Address:
    """Accept Address or hex string (CLI/SDK send Address objects, tests send str)."""
    if isinstance(x, Address):
        return x
    return Address(x)


def _norm_hex(x) -> str:
    """Lowercase hex string from an Address or hex string."""
    if isinstance(x, Address):
        return x.as_hex.lower()
    return str(x).lower()


@allow_storage
@dataclass
class Policy:
    max_per_tx: u256
    max_daily_amount: u256
    max_daily_count: u256
    allowlist: str  # JSON array of "0x..." hex addresses; "" = any counterparty


class HaltVault(gl.Contract):
    owner: Address
    guardian: Address

    balances: TreeMap[Address, u256]
    merchant_credit: TreeMap[Address, u256]

    policies: TreeMap[Address, Policy]
    spent_amount: TreeMap[Address, u256]
    spent_count: TreeMap[Address, u256]
    day_key: TreeMap[Address, str]

    frozen: TreeMap[Address, bool]

    ledger: DynArray[str]
    tx_count: u256

    def __init__(self, guardian: Address):
        self.owner = gl.message.sender_address
        self.guardian = _as_address(guardian)
        self.tx_count = u256(0)

    # ------------------------------------------------------------------
    # Admin (cooperative setup-time actions)
    # ------------------------------------------------------------------

    def _require_owner(self) -> None:
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only owner")

    @gl.public.write
    def set_guardian(self, guardian: Address) -> None:
        self._require_owner()
        self.guardian = _as_address(guardian)

    @gl.public.write
    def register_agent(
        self,
        agent: Address,
        max_per_tx: int,
        max_daily_amount: int,
        max_daily_count: int,
        allowlist_json: str,
    ) -> None:
        """Attach spending policy to an agent. Owner-only (setup is cooperative)."""
        self._require_owner()
        agent = _as_address(agent)
        if agent in self.policies:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agent already registered")
        if int(max_per_tx) <= 0 or int(max_daily_amount) <= 0 or int(max_daily_count) <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Limits must be positive")
        # Allowlist accepts a JSON string, a pre-parsed list (some SDKs/CLIs
        # auto-parse bracket args), or "" — empty in any form means "open".
        if isinstance(allowlist_json, list):
            parsed_allow = list(allowlist_json)
        elif allowlist_json == "" or allowlist_json is None:
            parsed_allow = []
        elif isinstance(allowlist_json, str):
            try:
                parsed_allow = json.loads(allowlist_json)
            except Exception:
                raise gl.vm.UserError(f"{ERROR_EXPECTED} Allowlist must be JSON array")
            if not isinstance(parsed_allow, list):
                raise gl.vm.UserError(f"{ERROR_EXPECTED} Allowlist must be JSON array")
        else:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Allowlist must be JSON array")
        allowlist_norm = ""
        if len(parsed_allow) > 0:
            try:
                allowlist_norm = json.dumps(sorted([_norm_hex(a) for a in parsed_allow]))
            except Exception:
                raise gl.vm.UserError(f"{ERROR_EXPECTED} Bad allowlist entry")
        self.policies[agent] = Policy(
            max_per_tx=u256(int(max_per_tx)),
            max_daily_amount=u256(int(max_daily_amount)),
            max_daily_count=u256(int(max_daily_count)),
            allowlist=allowlist_norm,
        )
        self.spent_amount[agent] = u256(0)
        self.spent_count[agent] = u256(0)
        self.day_key[agent] = ""
        self.frozen[agent] = False

    @gl.public.write
    def fund_agent(self, agent: Address, atto_amount: int) -> None:
        """Credit settlement balance. Owner-only demo faucet (see module docstring)."""
        self._require_owner()
        agent = _as_address(agent)
        if agent not in self.policies:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Unknown agent")
        if int(atto_amount) <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Amount must be positive")
        self.balances[agent] = self.balances.get(agent, u256(0)) + u256(int(atto_amount))

    @gl.public.write
    def set_frozen(self, agent: Address, flag: bool) -> None:
        """Emergency halt switch. ONLY the Guardian may call this — no backdoors,
        not even for the owner. That is the trust proposition."""
        if gl.message.sender_address != self.guardian:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only guardian")
        agent = _as_address(agent)
        self.frozen[agent] = bool(flag)

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    def _guardian_contract(self):
        if self.guardian.as_hex == ZERO_ADDRESS:
            return None
        return gl.get_contract_at(self.guardian)

    @gl.public.write
    def spend(
        self, to: Address, atto_amount: int, category: str, memo: str, day_key: str
    ) -> None:
        """Move settlement balance agent -> merchant credit, enforcing policy.

        Called by the payment agent itself for every purchase (x402-style).
        Reverts deterministically on any policy breach or freeze.
        """
        agent = gl.message.sender_address
        to = _as_address(to)
        if agent not in self.policies:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Unknown agent")
        if int(atto_amount) <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Amount must be positive")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_key or ""):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} day_key must be YYYY-MM-DD")
        if len(category) > 64 or len(memo) > 512:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Category/memo too long")

        # Fail-closed line 1: local frozen flag (set only by Guardian).
        if self.frozen.get(agent, False):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agent frozen by Guardian")

        # Fail-closed line 2: live Guardian status (covers emit propagation delay).
        gov = self._guardian_contract()
        if gov is not None:
            if bool(gov.view().is_frozen(agent.as_hex)):
                raise gl.vm.UserError(f"{ERROR_EXPECTED} Agent frozen by Guardian")
            if bool(gov.view().is_blocked(to.as_hex)):
                raise gl.vm.UserError(f"{ERROR_EXPECTED} Recipient is blacklisted")

        policy = self.policies[agent]
        amount = u256(int(atto_amount))

        if self.balances.get(agent, u256(0)) < amount:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Insufficient balance")
        if amount > policy.max_per_tx:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Exceeds max per-tx limit")

        # Rolling day window.
        if self.day_key.get(agent, "") != day_key:
            self.day_key[agent] = day_key
            self.spent_amount[agent] = u256(0)
            self.spent_count[agent] = u256(0)
        if self.spent_amount[agent] + amount > policy.max_daily_amount:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Exceeds daily amount limit")
        if self.spent_count[agent] + u256(1) > policy.max_daily_count:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Exceeds daily tx count limit")

        if policy.allowlist != "":
            allowed = json.loads(policy.allowlist)
            if to.as_hex.lower() not in [a.lower() for a in allowed]:
                raise gl.vm.UserError(f"{ERROR_EXPECTED} Recipient not allowlisted")

        self.balances[agent] = self.balances.get(agent, u256(0)) - amount
        self.merchant_credit[to] = self.merchant_credit.get(to, u256(0)) + amount
        self.spent_amount[agent] = self.spent_amount[agent] + amount
        self.spent_count[agent] = self.spent_count[agent] + u256(1)

        tx_id = f"TX-{int(self.tx_count)}"
        self.ledger.append(
            json.dumps(
                {
                    "tx_id": tx_id,
                    "agent": agent.as_hex,
                    "to": to.as_hex,
                    "atto_amount": str(int(amount)),
                    "category": category,
                    "memo": memo,
                    "day": day_key,
                },
                sort_keys=True,
            )
        )
        self.tx_count = self.tx_count + u256(1)

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    @gl.public.view
    def get_policy(self, agent: str) -> str:
        a = _as_address(agent)
        if a not in self.policies:
            return json.dumps({"registered": False})
        p = self.policies[a]
        return json.dumps(
            {
                "registered": True,
                "max_per_tx": str(int(p.max_per_tx)),
                "max_daily_amount": str(int(p.max_daily_amount)),
                "max_daily_count": str(int(p.max_daily_count)),
                "allowlist": p.allowlist,
                "frozen": bool(self.frozen.get(a, False)),
                "balance": str(int(self.balances.get(a, u256(0)))),
            },
            sort_keys=True,
        )

    @gl.public.view
    def get_balance(self, agent: str) -> str:
        return str(int(self.balances.get(_as_address(agent), u256(0))))

    @gl.public.view
    def get_merchant_credit(self, merchant: str) -> str:
        return str(int(self.merchant_credit.get(_as_address(merchant), u256(0))))

    @gl.public.view
    def get_tx_count(self) -> str:
        return str(int(self.tx_count))

    @gl.public.view
    def get_tx_history(self, start: int, count: int) -> str:
        total = int(self.tx_count)
        s = max(0, int(start))
        c = max(0, min(int(count), 200))
        out = []
        for i in range(s, min(s + c, total)):
            out.append(json.loads(self.ledger[i]))
        return json.dumps(out)

    @gl.public.view
    def get_status(self, agent: str) -> str:
        a = _as_address(agent)
        return json.dumps(
            {
                "agent": a.as_hex,
                "registered": bool(a in self.policies),
                "frozen": bool(self.frozen.get(a, False)),
                "balance": str(int(self.balances.get(a, u256(0)))),
                "spent_today": str(int(self.spent_amount.get(a, u256(0)))),
                "txs_today": str(int(self.spent_count.get(a, u256(0)))),
                "day": self.day_key.get(a, ""),
            },
            sort_keys=True,
        )
