// kami web: Next server proxies the optional simulation service. The Mapbox token comes from web/.env.local (not committed);
// NEXT_PUBLIC_MAPBOX_TOKEN is the standard name, a few common names are mapped onto it.
const token =
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN ||
  process.env.MAPBOX_PUBLIC_TOKEN ||
  process.env.MAPBOX_TOKEN ||
  process.env.MAPBOX_ACCESS_TOKEN ||
  process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN ||
  "";

import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const origin = new URL(process.env.KAMI_SERVICE_URL || "http://127.0.0.1:8000");
    if (!["http:", "https:"].includes(origin.protocol) || origin.pathname !== "/" || origin.search || origin.hash || origin.username || origin.password) throw new Error("KAMI_SERVICE_URL must be an HTTP(S) origin");
    return [{ source: "/api/v1/:path*", destination: origin.origin + "/api/v1/:path*" }];
  },
  reactStrictMode: true,
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_MAPBOX_TOKEN: token },
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) },
};

export default nextConfig;
