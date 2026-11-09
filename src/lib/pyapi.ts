// Typed client for the AdPilot AI Python FastAPI backend.
//
// The sandbox gateway (Caddy) forwards any request containing the
// `XTransformPort` query parameter to localhost:<port>. The backend listens
// on 8321 and serves everything under /api/v1. In local (non-sandbox) runs,
// set NEXT_PUBLIC_API_BASE_URL=http://localhost:8321 instead.

export const BACKEND_PORT = 8321;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export function pyUrl(path: string): string {
  const sep = path.includes("?") ? "&" : "?";
  if (API_BASE) return `${API_BASE}${path}`;
  return `${path}${sep}XTransformPort=${BACKEND_PORT}`;
}

export async function pyFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(pyUrl(path), {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      detail = body?.error?.message ?? body?.detail ?? JSON.stringify(body);
    } catch {
      /* keep status code */
    }
    throw new Error(`AdPilot API error: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const ensureBackend = () =>
  fetch("/api/py-health").then((r) => r.json()) as Promise<{
    healthy: boolean;
    spawned?: boolean;
    detail?: string;
  }>;

export function reportDownloadUrl(reportId: number): string {
  return pyUrl(`/api/v1/reports/${reportId}/download`);
}

export function chartUrl(name: string): string {
  return pyUrl(`/api/v1/bigdata/charts/${encodeURIComponent(name)}`);
}
