import { chains, createAccount, createClient, generatePrivateKey } from "genlayer-js";

const GUARDIAN = process.env.HALT_GUARDIAN as string;
const VAULT = process.env.HALT_VAULT as string;

// Studio Devnet (chain 61997) — the release-candidate Studio environment the
// stewards asked this deployment to target. genlayer-js ships the matching
// preset (RPC + consensus deployment bound together); never relabel the
// stable studionet preset for this chain.
const studioDevnet = (chains as unknown as { studioDevnet: unknown }).studioDevnet;

type Client = ReturnType<typeof createClient>;
let _client: Client | null = null;

export function client(): Client {
  if (!_client) {
    // Reads need a `from` address; an ephemeral unfunded key is enough.
    const reader = createAccount(generatePrivateKey());
    _client = createClient({ chain: studioDevnet as never, account: reader as never });
  }
  return _client;
}

export async function read(address: string, functionName: string, args: unknown[] = []) {
  const c = client() as unknown as {
    readContract: (p: { address: string; functionName: string; args: unknown[] }) => Promise<unknown>;
  };
  return c.readContract({ address, functionName, args });
}

export function addrs() {
  return { GUARDIAN, VAULT };
}
