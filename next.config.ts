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
};

export default nextConfig;
