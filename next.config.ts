import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  output: "standalone",
  // Pin the Turbopack workspace root to this project. Without this, Turbopack
  // infers the root from lockfiles up the tree and can fail with
  // "Next.js inferred your workspace root, but it may not be correct".
  turbopack: {
    root: path.join(__dirname),
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  // Proxy backend API calls at the Next.js layer. The client lib appends
  // ?XTransformPort=8321 (sandbox gateway routing); with this rewrite the
  // same URLs ALSO resolve when the app is opened directly on :3000 —
  // localhost, LAN IP or any host without the gateway. FastAPI ignores the
  // extra query parameter, so one URL shape serves every access path.
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8321/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
