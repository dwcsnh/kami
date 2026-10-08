// kami web (sprint 03): static export, no backend. The Mapbox token comes from web/.env.local (not committed);
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
  output: "export",
  reactStrictMode: true,
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_MAPBOX_TOKEN: token },
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) },
};

export default nextConfig;
