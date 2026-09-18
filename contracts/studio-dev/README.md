# Studio Dev (chain 61997) contracts

These are the release-candidate ports of HALT, deployed on **GenLayer Studio Dev**
(`https://studio-dev.genlayer.com/api`, chain 61997) as requested in steward review.
The canonical (stable studionet, 61999) originals remain in `contracts/`.

Live deployment (studio-dev):

- HaltGuardian: `0x38790445fe9eDd74e5420D84ee9A5511a547aC12`
- HaltVault: `0xBc9c5199462e6E1D16147Eccbe49056eB1192052`

## What differs from the stable version

The RC consensus stack (GenVM v0.3.0 + runner `5jycge4q…`) changes several SDK idioms:

| Concern | Stable (61999) | Studio Dev (61997) |
|---|---|---|
| Runner pin | `1jb45aa8…` | `5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` |
| Import style | `from genlayer import *` | `import genlayer as gl` + `from genlayer.types import *` |
| Contract base | `gl.Contract` | `gl.contract.Contract` |
| Storage containers | builtins `TreeMap`/`DynArray` | `from genlayer.storage import TreeMap, DynArray` |
| Storage dataclasses | `@allow_storage` | `@gl.storage.allow` |
| Cross-contract read | `gl.get_contract_at(addr)` | `gl.contract.get_at(addr)` (+`.view()`) |
| Custom validator | `gl.vm.run_nondet_unsafe(leader, validator)` | `gl.eq_principle.prompt_comparative(fn, principle)` |
| Cross-contract write | `vault.emit(on="accepted").set_frozen(...)` | **not used** — see below |
| Transactions | gasless | fee-aware; fee deposit required per consensus tx |

### Why the vault derives freeze state instead of the guardian emitting it

The RC stack requires an explicit message-fee allocation for internal messages
(`emit(...)`), and the guardian's enforcement call failed at the WASI layer
(`SystemError: 2: inval`) without one. Enforcement therefore relies on the
already-present fail-closed view path: `HaltVault.spend()` calls
`guardian.is_frozen(agent)` on every outflow, and the vault's display views
(`get_policy`, `get_status`) derive `frozen` live from that same source of truth.
Freeze and unfreeze take effect atomically with the guardian's state, with no
message plumbing — and no way for the vault's cached flag to disagree with the
guardian.

The rest of the design is unchanged: deterministic `rule` engine, LLM `behavior`
engine, freeze-first/appeal-after lifecycle, bounty/slash economics, attacker
blacklist with expungement on overturn.

## Deploying / driving this variant

Writes on Studio Dev must be fee-aware. The CLI alone sends `feeValue = 0` and is
rejected (`FeeValueMustBeNonZero`); use the RC `genlayer-js` client
(2.0.0-rc.1), which estimates the deposit via Studio simulation:

```js
import { createClient, createAccount } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

const client = createClient({ chain: studioDevnet, account });
const fees = await client.estimateTransactionFeesForWrite({
  address, functionName, args,
});
await client.writeContract({ address, functionName, args, fees });
```

The deploy itself uses `client.estimateTransactionFees()` as the `fees` argument
to `deployContract`. A funded account is required (Studio Dev faucet: the 💧
button at `studio-dev.genlayer.com`).
