import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_PORT = 8317;

type BackendRef = { child: ChildProcess | null; starting: boolean };
const g = globalThis as typeof globalThis & { __reviewIntelBackend?: BackendRef };
if (!g.__reviewIntelBackend) g.__reviewIntelBackend = { child: null, starting: false };
const ref = g.__reviewIntelBackend;

function isHealthy(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port: BACKEND_PORT, path: "/api/health", timeout: 1500 },
      (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      },
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

function childAlive(c: ChildProcess | null): boolean {
  return !!c && c.exitCode === null && !c.killed;
}

/**
 * Spawn uvicorn as a REGULAR child of the persistent next-server process.
 * No detach/no setsid: the sandbox reaps detached session leaders, but keeps
 * children inside the managed process tree alive.
 */
function spawnBackend(): ChildProcess {
  const logFile = path.join(process.cwd(), "backend", "uvicorn.log");
  fs.mkdirSync(path.dirname(logFile), { recursive: true });
  const out = fs.openSync(logFile, "a");
  const child = spawn(
    "python3",
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    {
      cwd: path.join(process.cwd(), "backend"),
      stdio: ["ignore", out, out],
      env: { ...process.env, PYTHONFAULTHANDLER: "1", PYTHONUNBUFFERED: "1" },
    },
  );
  child.on("exit", () => {
    if (ref.child === child) ref.child = null;
  });
  ref.child = child;
  return child;
}

async function waitHealthy(maxMs: number): Promise<boolean> {
  const started = Date.now();
  for (;;) {
    if (await isHealthy()) return true;
    if (Date.now() - started > maxMs) return false;
    await new Promise((r) => setTimeout(r, 600));
  }
}

/**
 * Node-runtime route executed inside the persistent next-server process.
 * Ensures the Python backend is alive: health-check -> spawn -> wait.
 * Idempotent and safe to call on every app load.
 */
export async function GET() {
  if (await isHealthy()) {
    return NextResponse.json({ healthy: true, spawned: false });
  }
  if (ref.starting) {
    const ok = await waitHealthy(25000);
    return NextResponse.json({ healthy: ok, spawned: false, concurrent: true });
  }
  ref.starting = true;
  try {
    // stale process object but port dead -> it crashed; clear handle
    ref.child = null;
    const child = spawnBackend();
    const healthy = await waitHealthy(25000);
    return NextResponse.json({ healthy, spawned: true, pid: child.pid });
  } finally {
    ref.starting = false;
  }
}
