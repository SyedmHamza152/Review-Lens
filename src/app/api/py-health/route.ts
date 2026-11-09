import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_PORT = 8321;
const PYTHON = process.env.ADPILOT_PYTHON ?? "python3";

type BackendRef = { child: ChildProcess | null; starting: boolean };
const g = globalThis as typeof globalThis & { __adpilotBackend?: BackendRef };
if (!g.__adpilotBackend) g.__adpilotBackend = { child: null, starting: false };
const ref = g.__adpilotBackend;

function isHealthy(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port: BACKEND_PORT, path: "/api/v1/health", timeout: 1500 },
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
 * Spawn uvicorn as a regular child of the persistent next-server process
 * (no detach/setsid: the sandbox reaps detached session leaders). A local
 * venv is preferred when present; the system python is the fallback.
 */
function spawnBackend(): ChildProcess {
  const backendDir = path.join(process.cwd(), "backend");
  const logFile = path.join(backendDir, "uvicorn.log");
  fs.mkdirSync(path.dirname(logFile), { recursive: true });
  const out = fs.openSync(logFile, "a");

  // Runtime-resolved path (spread keeps the bundler from tracing the venv
  // symlink, which lives outside the project root).
  const venvParts: string[] = [".venv", "bin", "python"];
  const venvPython = path.join(backendDir, ...venvParts);
  const useVenv = fs.existsSync(venvPython);
  const cmd = useVenv ? venvPython : PYTHON;

  const child = spawn(
    cmd,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    {
      cwd: backendDir,
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

/** Idempotent: health-check -> spawn -> wait. Safe to call on every load. */
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
    if (!childAlive(ref.child)) ref.child = null;
    const child = spawnBackend();
    const healthy = await waitHealthy(25000);
    return NextResponse.json({ healthy, spawned: true, pid: child.pid });
  } catch (e) {
    return NextResponse.json({ healthy: false, detail: String(e) }, { status: 500 });
  } finally {
    ref.starting = false;
  }
}
