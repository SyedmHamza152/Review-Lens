#!/usr/bin/env bash
# Preflight for `bun run dev` — self-heals the environment after sandbox
# recycles (which can wipe node_modules). Fast no-op when everything exists.
cd "$(dirname "$0")/.." || exit 0

if [ ! -f node_modules/next/dist/bin/next ]; then
  echo "[adpilot-preflight] node_modules missing — installing…"
  bun install 2>&1 | tail -1
fi
exit 0
