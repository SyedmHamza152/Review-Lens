#!/bin/bash
# AdPilot AI backend launcher — used by the sandbox dev script (dev.sh scans
# mini-services/*/package.json) and usable standalone.
# Idempotent: if the backend already answers on :8321, this exits quietly.
set -u
cd "$(dirname "$0")/../.."

PORT=8321

if curl -s --max-time 2 "http://127.0.0.1:${PORT}/api/v1/health" > /dev/null 2>&1; then
  echo "[adpilot-backend] already healthy on :${PORT}"
  exit 0
fi

PY="backend/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "[adpilot-backend] venv missing — creating backend/.venv and installing requirements (one-time)"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install --upgrade pip -q
  backend/.venv/bin/pip install -r backend/requirements.txt -q
fi

echo "[adpilot-backend] starting uvicorn on :${PORT}"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --app-dir backend
