// AC03-3 / AC03-5: the TypeScript look-ups reproduce kami.replay.query (samples written by
// tests/data/replay/make_web_samples.py) and the engine's time series.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { checkManifest, parseBytes } from "./loader";
import { Replay, bucketCounts, formatClock } from "./replay";
import { loadFolder } from "./testing";
import type { Manifest } from "./types";

const DIR = join(__dirname, "__fixtures__", "grid_small");
const DEMO = join(__dirname, "..", "..", "public", "fixtures", "hanoi_center_demo");

interface Samples {
  positions: { vehicle: number; t: number; state: string | null; pos: [number, number] | null }[];
  metrics: { t: number; row: number | null }[];
}

let rp: Replay;
let samples: Samples;

beforeAll(async () => {
  rp = new Replay(await loadFolder(DIR));
  samples = JSON.parse(readFileSync(join(DIR, "samples.json"), "utf8"));
});

describe("Replay look-ups match the Python reference", () => {
  it("stateAt / positionAt", () => {
    expect(samples.positions.length).toBe(200);
    let online = 0;
    for (const s of samples.positions) {
      const vi = rp.vehicleIndex.get(s.vehicle)!;
      const st = rp.stateAt(vi, s.t);
      expect(st < 0 ? null : rp.states[st].id, `vehicle ${s.vehicle} t=${s.t}`).toBe(s.state);
      const p = rp.positionAt(vi, s.t);
      if (s.pos === null) expect(p).toBeNull();
      else {
        online++;
        expect(p![0]).toBeCloseTo(s.pos[0], 5);
        expect(p![1]).toBeCloseTo(s.pos[1], 5);
      }
    }
    expect(online).toBeGreaterThan(100);
  });

  it("metricsAt = last row with t_row ≤ t", () => {
    for (const s of samples.metrics) {
      const r = rp.metricsRowAt(s.t);
      expect(r < 0 ? null : r).toBe(s.row);
      const m = rp.metricsAt(s.t);
      if (s.row === null) expect(m).toBeNull();
      else {
        expect(m!.t).toBe(rp.metrics.t[s.row]);
        expect(m!["rider.completed_cum"]).toBe(rp.metrics.series["rider.completed_cum"][s.row]);
      }
    }
  });
});

describe("Replay structure", () => {
  it("segments of a vehicle are contiguous and cover its shift", () => {
    for (let vi = 0; vi < rp.vehicles.length; vi++) {
      const v = rp.vehicles[vi];
      const a = rp.vehStart[vi];
      const n = rp.vehCount[vi];
      expect(rp.segT0[a]).toBe(v.shift[0]);
      expect(rp.segT1[a + n - 1]).toBe(v.shift[1]);
      for (let k = a; k < a + n - 1; k++) expect(Math.abs(rp.segT1[k] - rp.segT0[k + 1])).toBeLessThan(0.11);
    }
  });

  it("path batches hold every moving segment once, timestamps relative to the start", () => {
    const batches = rp.pathBatches();
    expect(batches.length).toBe(rp.states.length);
    let moving = 0;
    for (let i = 0; i < rp.segmentCount; i++) if (rp.segLen[i] > 1) moving++;
    expect(batches.reduce((s, b) => s + b.length, 0)).toBe(moving);
    for (const b of batches) for (let k = 0; k < b.timestamps.length; k++) expect(b.timestamps[k]).toBeGreaterThanOrEqual(0);
  });

  it("distance driven grows with time and ends at the sum of segment distances", () => {
    for (let vi = 0; vi < rp.vehicles.length; vi++) {
      let prev = 0;
      for (let t = rp.start; t <= rp.end; t += 37) {
        const d = rp.distanceAt(vi, t);
        expect(d).toBeGreaterThanOrEqual(prev - 1e-6);
        prev = d;
      }
      const a = rp.vehStart[vi];
      const n = rp.vehCount[vi];
      let total = 0;
      for (let k = a; k < a + n; k++) total += rp.segDist[k];
      expect(rp.distanceAt(vi, rp.end + 1)).toBeCloseTo(total, 6);
    }
  });

  it("rider trips are indexed from events", () => {
    const i = rp.events.type.indexOf("dropoff");
    const r = rp.rider(rp.events.rider[i])!;
    expect(r.request).toBeLessThanOrEqual(r.matched!);
    expect(r.matched).toBeLessThanOrEqual(r.pickup!);
    expect(r.pickup).toBeLessThanOrEqual(r.dropoff!);
    expect(r.eta).toBeDefined();
  });

  it("15-minute buckets add up to the cumulative counters", () => {
    const b = bucketCounts(rp.metrics, 900);
    const last = rp.metrics.t.length - 1;
    expect(b.completed.reduce((a, x) => a + x, 0)).toBe(rp.metrics.series["rider.completed_cum"][last]);
    expect(b.cancelled.reduce((a, x) => a + x, 0)).toBe(rp.metrics.series["rider.cancelled_cum"][last]);
  });

  it("state counts per time add up to the online vehicles", () => {
    const [c] = rp.stateCounts([rp.start + 600]);
    let online = 0;
    for (let vi = 0; vi < rp.vehicles.length; vi++) if (rp.segmentAt(vi, rp.start + 600) >= 0) online++;
    expect(c.reduce((a, x) => a + x, 0)).toBe(online);
  });
});

describe("loader", () => {
  it("parses gzip and plain JSON", async () => {
    const raw = readFileSync(join(DIR, "vehicles.json.gz"));
    const a = await parseBytes(new Uint8Array(raw));
    const b = await parseBytes(new TextEncoder().encode(JSON.stringify(a)));
    expect(b).toEqual(a);
  });

  it("refuses a newer schema version and accepts unknown fields", () => {
    const m = JSON.parse(readFileSync(join(DIR, "manifest.json"), "utf8")) as Manifest;
    expect(() => checkManifest({ ...m, extra: 1 } as Manifest)).not.toThrow();
    expect(() => checkManifest({ ...m, schema_version: 2 })).toThrow(/newer/);
  });

  it("formats the simulation clock", () => {
    expect(formatClock(7 * 3600 + 5 * 60 + 9)).toBe("07:05:09");
    expect(formatClock(9 * 3600, false)).toBe("09:00");
  });
});

describe("demo fixture (web/public/fixtures/hanoi_center_demo)", () => {
  it("loads, 300 vehicles inside Hà Nội", async () => {
    const demo = new Replay(await loadFolder(DEMO));
    expect(demo.vehicles.length).toBe(300);
    expect(demo.manifest.coords).toBe("lonlat");
    const [x0, y0, x1, y1] = demo.manifest.bounds!;
    expect(x0).toBeGreaterThan(105.7);
    expect(x1).toBeLessThan(105.95);
    expect(y0).toBeGreaterThan(20.9);
    expect(y1).toBeLessThan(21.1);
  });
});
