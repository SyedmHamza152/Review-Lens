// Typed client for the Python FastAPI backend.
//
// The sandbox gateway (Caddy) forwards any request containing the
// `XTransformPort` query parameter to localhost:<port>. The Python backend
// listens on 8317 and serves everything under /api.

export const BACKEND_PORT = 8317;

export function pyUrl(path: string): string {
  const sep = path.includes("?") ? "&" : "?";
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
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      /* keep status code */
    }
    throw new Error(`Backend API error: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const ensureBackend = () => fetch("/api/py-health").then((r) => r.json());

export function exportUrl(jobId: string, kind: "csv" | "pdf"): string {
  return pyUrl(`/api/jobs/${jobId}/export.${kind}`);
}
