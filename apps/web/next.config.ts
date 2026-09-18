import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Pin the workspace root: a stray package-lock.json in the user's home dir
  // otherwise makes Next infer the wrong root and break output tracing.
  outputFileTracingRoot: path.join(__dirname),
  async rewrites() {
    // Browser calls /api/v1/* -> FastAPI on :8000 (same-origin from the page's view).
    const api =
      process.env.VIRAM_API_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${api}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
