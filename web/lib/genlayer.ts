import { chains, createAccount, createClient, generatePrivateKey } from "genlayer-js";

const GUARDIAN = process.env.HALT_GUARDIAN as string;
const VAULT = process.env.HALT_VAULT as string;

// genlayer-js 0.9.0 ships no studionet preset: reuse the bundled consensus
// ABIs with studionet's chain id, RPC and consensus contract addresses.
const _t = (chains as unknown as { testnetAsimov: unknown }).testnetAsimov as unknown as {
  consensusMainContract: { abi: never[] };
  consensusDataContract: { abi: never[] };
};
const studionet = {
  id: 61999,
  name: "Genlayer Studio Network",
  nativeCurrency: { name: "GEN Token", symbol: "GEN", decimals: 18 },
  rpcUrls: { default: { http: ["https://studio.genlayer.com/api"] } },
  blockExplorers: {
    default: { name: "GenLayer Explorer", url: "https://genlayer-explorer.vercel.app" },
  },
  testnet: true,
  consensusMainContract: {
    address: "0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575",
    abi: _t.consensusMainContract.abi,
    bytecode: "",
  },
  consensusDataContract: {
    address: "0x88B0F18613Db92Bf970FfE264E02496e20a74D16",
    abi: _t.consensusDataContract.abi,
    bytecode: "",
  },
  defaultNumberOfInitialValidators: 5,
  defaultConsensusMaxRotations: 3,
};

type Client = ReturnType<typeof createClient>;
let _client: Client | null = null;

export function client(): Client {
  if (!_client) {
    // Reads need a `from` address; an ephemeral unfunded key is enough.
    const reader = createAccount(generatePrivateKey());
    _client = createClient({ chain: studionet as never, account: reader as never });
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
