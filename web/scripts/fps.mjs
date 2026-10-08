// AC03-6 (plan D16): frame rate of the visualizer while playing the demo fixture at 60×, 60 s per zoom level,
// in the system Chrome **with the GPU** (headless=new + ANGLE). Prints the GPU renderer and median / p5 fps.
//   npm run dev   then   node scripts/fps.mjs [baseUrl] [seconds]
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://localhost:3000";
const seconds = Number(process.argv[3] ?? 60);
const extra = process.env.EXTRA ? `&${process.env.EXTRA}` : "";
const CASES = [
  ["toàn khu vực, zoom 12", "105.835,21.0225,12,0,0"],
  ["quận, zoom 14", "105.845,21.025,14,0,0"],
  ["phố, zoom 16 nghiêng 60°", "105.8455,21.0245,16,60,-20"],
];

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  args: ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=" + (process.env.ANGLE ?? "vulkan"),
         "--enable-features=Vulkan", "--disable-frame-rate-limit=false"],
});
const results = [];
for (const [name, view] of CASES) {
  if (process.env.ONLY && !name.includes(process.env.ONLY)) continue;
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(`${base}/?t=27000&view=${view}${extra}`, { waitUntil: "load" });
  await page.waitForFunction(() => window.__kamiMapIdle === true, null, { timeout: 180000 });
  const renderer = await page.evaluate(() => {
    const gl = document.createElement("canvas").getContext("webgl2");
    const ext = gl?.getExtension("WEBGL_debug_renderer_info");
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "unknown";
  });
  const r = await page.evaluate(async (sec) => {
    const st = window.__kami.store.getState();
    st.setSpeed(60);
    st.setPlaying(true);
    const d = [];
    let last = performance.now();
    await new Promise((done) => {
      const end = last + sec * 1000;
      const f = (now) => { d.push(now - last); last = now; if (now < end) requestAnimationFrame(f); else done(); };
      requestAnimationFrame(f);
    });
    window.__kami.store.getState().setPlaying(false);
    const fps = d.slice(5).map((x) => 1000 / x).sort((a, b) => a - b);
    const q = (p) => fps[Math.min(fps.length - 1, Math.round(p * (fps.length - 1)))];
    return { frames: fps.length, median: q(0.5), p5: q(0.05), tEnd: window.__kami.store.getState().t };
  }, seconds);
  results.push({ name, renderer, ...r });
  console.log(`${name}: median ${r.median.toFixed(1)} fps, p5 ${r.p5.toFixed(1)} fps, ${r.frames} frames — ${renderer}`);
  await page.close();
}
await browser.close();
console.log(JSON.stringify(results));
