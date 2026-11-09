#!/usr/bin/env bash
# AdPilot AI — stable stack: production Next server + standalone uvicorn.
# Lighter than dev mode (avoids sandbox OOM recycles). Safe to re-run.
set -u
cd "$(dirname "$0")/.." || exit 1

log() { echo "[adpilot-stack] $*"; }

# 0. Dependencies
if [ ! -f node_modules/next/dist/bin/next ]; then
  log "node_modules missing — running bun install…"
  bun install 2>&1 | tail -1
fi

# 1. Backend first (independent of the web server)
if ! curl -s -m 3 -o /dev/null http://127.0.0.1:8321/api/v1/health; then
  log "starting backend (uvicorn)…"
  nohup backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8321 \
    --app-dir backend >> backend/uvicorn.log 2>&1 &
  for i in $(seq 1 30); do
    curl -s -m 3 -o /dev/null http://127.0.0.1:8321/api/v1/health && break
    sleep 1
  done
fi
curl -s -m 5 http://127.0.0.1:8321/api/v1/health >/dev/null && log "backend: up" || log "backend: DOWN"

# 2. Production frontend (standalone build) on port 3000
if ! curl -s -m 3 -o /dev/null http://localhost:3000/; then
  log "starting Next production server…"
  pkill -f "next dev" 2>/dev/null; pkill -f next-server 2>/dev/null; sleep 1
  if [ ! -f .next/standalone/server.js ]; then
    log "standalone build missing — building…"
    bun run build 2>&1 | tail -2
  fi
  (cd .next/standalone && PORT=3000 HOSTNAME=0.0.0.0 nohup node server.js > ../../server.log 2>&1 &)
  for i in $(seq 1 30); do
    curl -s -m 3 -o /dev/null http://localhost:3000/ && break
    sleep 1
  done
fi
code=$(curl -s -m 10 -o /dev/null -w "%{http_code}" http://localhost:3000/)
log "frontend: HTTP $code"
