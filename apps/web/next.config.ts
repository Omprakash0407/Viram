import type { NextConfig } from "next";
import path from "node:path";

/**
 * Two build modes:
 *
 * 1. Normal (default): the Next server proxies browser /api/v1/* calls to the
 *    FastAPI backend (VIRAM_API_URL, default http://localhost:8000).
 *
 * 2. Static export (STATIC_EXPORT_BASE_PATH set): GitHub Pages deployment.
 *    Pages serves files only — no Next server, no API proxy. The Explore pages
 *    are prerendered at build time from the running API (VIRAM_EXPORT_API_URL),
 *    so the exported site works as a self-contained demo; account/booking
 *    features show an honest "needs the live backend" note (AuthPanel banner).
 */
const basePath = process.env.STATIC_EXPORT_BASE_PATH;

const nextConfig: NextConfig = {
  // Pin the workspace root: a stray package-lock.json in the user's home dir
  // otherwise makes Next infer the wrong root and break output tracing.
  outputFileTracingRoot: path.join(__dirname),

  ...(basePath
    ? {
        basePath,
        output: "export" as const,
        // Pages is file-serving only; without this every next/image becomes a
        // request to a non-existent optimizer endpoint.
        images: { unoptimized: true },
        trailingSlash: true,
      }
    : {}),

  async rewrites() {
    if (basePath) return [];
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
