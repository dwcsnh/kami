// Screenshots for docs/engine/20-visualizer.md (and the palette choice, plan D12):
//   npm run dev   (in another terminal)   then   node scripts/screenshots.mjs [baseUrl] [outDir] [--only name,...]
// Uses the system Chrome through playwright-core (no browser download). The map must have a Mapbox token.
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const args = process.argv.slice(2);
const only = args.includes("--only") ? args[args.indexOf("--only") + 1].split(",") : null;
const pos = args.filter((a, i) => !a.startsWith("--") && args[i - 1] !== "--only");
const base = pos[0] ?? "http://localhost:3000";
const out = pos[1] ?? fileURLToPath(new URL("../../docs/engine/img/visualizer/", import.meta.url));
mkdirSync(out, { recursive: true });

const AREA = "105.835,21.0225";
const SHOTS = [
  // name, query, viewport
  ["overview", "t=28800", [1440, 900]],
  ["overview-1280", "t=28800", [1280, 800]],
  ["trajectories", "t=30600&mode=trajectories", [1440, 900]],
  ["tilt-3d", "t=28800&view=105.8455,21.0245,16,55,-20", [1440, 900]],
  ["zoom16-street", "t=28800&view=105.8505,21.0275,16.5,0,0&panel=0", [1440, 900]],
  ["vehicle-detail", "t=28920&select=142&view=105.8433,21.0201,14.6,0,0", [1440, 900]],
  ["toggle-states", "t=28800&hide=on_trip,idle&view=" + AREA + ",13.4,0,0", [1440, 900]],
  ["panels-hidden", "t=28800&panel=0", [1440, 900]],
  ["od-arcs", "t=28800&od=1&view=" + AREA + ",13.2,40,0", [1440, 900]],
  ["palette-A-z12", "t=28800&palette=A&panel=0&view=" + AREA + ",12.4,0,0", [1440, 900]],
  ["palette-B-z12", "t=28800&palette=B&panel=0&view=" + AREA + ",12.4,0,0", [1440, 900]],
  ["palette-A-z15", "t=28800&palette=A&panel=0&view=105.848,21.026,15,0,0", [1440, 900]],
  ["palette-B-z15", "t=28800&palette=B&panel=0&view=105.848,21.026,15,0,0", [1440, 900]],
  ["components", null, [1280, 1800], "/ui"],
];

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
for (const [name, q, [w, h], path] of SHOTS) {
  if (only && !only.includes(name)) continue;
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const url = `${base}${path ?? "/"}${q ? `?${q}` : ""}`;
  await page.goto(url, { waitUntil: "load" });
  if (!path) {
    await page.waitForFunction(() => window.__kamiMapIdle === true, null, { timeout: 180000 });
    await page.waitForTimeout(1500);
  } else {
    await page.waitForTimeout(1500);
  }
  await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });   // Next.js dev indicator
  await page.screenshot({ path: join(out, `${name}.png`), fullPage: !!path });
  console.log(`${name}.png  ←  ${url}`);
  await page.close();
}
await browser.close();
