#!/bin/bash
# HALT studionet setup: wire contracts, fund accounts, register agent.
# Usage: PW=<keystore-password> ./scripts/studionet_setup.sh <guardian> <vault>
# Paces transactions (~25s apart) to respect studionet pending-queue caps.
set -u
G=${1:?guardian address required}
V=${2:?vault address required}
PW=${PW:?set PW env var}
A=0xd2982f73dd841ecffc850500919b8eb3c91ee1b6
W=0x3e82eafb69ec2e51eeca290591637adb340f9865
M=0x4585ec1205119c9968d8a31aaae33559248c59fa

wx() { # wx <account> <address> <method> [args...]
  local acct=$1 addr=$2 method=$3; shift 3
  genlayer account use "$acct" > /dev/null 2>&1
  if [ $# -eq 0 ]; then
    echo "$PW" | genlayer write "$addr" "$method" 2>&1 \
      | grep -E "successfully executed|Error during" | head -1
  else
    echo "$PW" | genlayer write "$addr" "$method" --args "$@" 2>&1 \
      | grep -E "successfully executed|Error during" | head -1
  fi
  sleep 25
}

echo "== set_vault =="
wx owner "$G" set_vault "$V"
echo "vault on guardian: $(genlayer call "$G" get_vault 2>/dev/null | grep -E '^Result' -A1 | tail -1)"

echo "== economics =="
wx owner "$G" mint_credits "$A" 1000
wx owner "$G" mint_credits "$W" 50
wx owner "$G" mint_credits "$M" 1000
wx owner "$G" fund_pool 100
echo "pool: $(genlayer call "$G" get_pool 2>/dev/null | grep -E '^Result' -A1 | tail -1)"
echo "agent credits: $(genlayer call "$G" get_credits --args "$A" 2>/dev/null | grep -E '^Result' -A1 | tail -1)"

echo "== vault policy =="
wx owner "$V" register_agent "$A" 50 200 10 "[\"$M\"]"
wx owner "$V" fund_agent "$A" 1000
echo "policy: $(genlayer call "$V" get_policy --args "$A" 2>/dev/null | grep -E '^Result' -A1 | tail -1)"

echo "== agent + watchdog registration =="
wx agent "$G" register_agent "shopper-1" "$A" "Only buy office supplies from approved vendors. Never send funds to unknown addresses. Max 50 credits per purchase, 200 per day."
wx watchdog "$G" register_watchdog
echo "stats: $(genlayer call "$G" get_stats 2>/dev/null | grep -E '^Result' -A1 | tail -1)"
echo "DONE"
