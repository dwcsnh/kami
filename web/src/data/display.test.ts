import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { ReplayDisplay } from "./display";
import { Replay } from "./replay";
import { loadFolder } from "./testing";
import type { ReplayDocs } from "./types";
import { computeFrame } from "@/map/frame";
import { stateRgb } from "@/map/palette";
import { buildLayers } from "@/map/layers";
import { layerPlan } from "@/map/layerPlan";
import { TextLayer } from "@deck.gl/layers";

let docs: ReplayDocs, rp: Replay, display: ReplayDisplay;
beforeAll(async () => {
  docs = await loadFolder(join(__dirname, "..", "..", "public", "fixtures", "shared_v1_demo"));
  rp = new Replay(docs); display = new ReplayDisplay(rp);
});

describe("shared vehicles and waiting-request display", () => {
  it("only categorizes active pairs as shared, including pickup and after the first dropoff", () => {
    const pair = docs.manifest.shared!.pairs[0], vi = rp.vehicleIndex.get(pair.driver_id)!;
    for (const t of [pair.created_t, pair.overlap_start!, pair.overlap_end! + 1]) {
      expect(display.states[display.stateAt(vi, t)].id).toBe("shared");
    }
    for (const t of [pair.created_t - 1, pair.closed_t!]) {
      expect(display.states[display.stateAt(vi, t)].id).not.toBe("shared");
    }
    // The underlying engine/replay state and cohort metrics are unchanged.
    expect(rp.states).toHaveLength(docs.manifest.states.length);
    expect(display.states).toHaveLength(rp.states.length + 1);
  });

  it("isolates shared dots and counts without double-counting or depending on the ordinary states", () => {
    const t = docs.manifest.shared!.pairs[0].overlap_start! + 1;
    const colors = stateRgb(display.states, "A"), shared = display.stateIndex.get("shared")!;
    const onlyShared = display.states.map(s => s.id === "shared");
    const frame = computeFrame(rp, t, onlyShared, colors, undefined, display);
    expect(frame.length).toBeGreaterThan(0);
    expect(frame.length).toBe(frame.counts[shared]);
    expect(Array.from(frame.counts).reduce((a, b) => a + b, 0)).toBe(frame.online);
    for (let k = 0; k < frame.length; k++) expect(display.stateAt(frame.vehicle[k], t)).toBe(shared);
    const noShared = computeFrame(rp, t, onlyShared.map(v => !v), colors, undefined, display);
    for (let k = 0; k < noShared.length; k++) expect(display.stateAt(noShared.vehicle[k], t)).not.toBe(shared);
    const hidden = Object.fromEntries(display.states.map(s => [s.id, s.id !== "shared"]));
    const plan = layerPlan({ states: display.states.map(s => s.id), hidden, mode: "vehicles", elapsed: 400,
      selected: frame.vehicle[0], selectedVisible: false, showOD: false });
    expect(plan.filter(p => p.kind === "trail").map(p => p.id)).toEqual(["trail-shared"]);
    expect(plan.some(p => p.kind === "selected")).toBe(false);
  });

  it("clips a moving path exactly at shared start/end, also for accumulated trajectories", () => {
    const custom = structuredClone(docs), pair = custom.manifest.shared!.pairs[0];
    custom.manifest.shared!.pairs = [{ ...pair, created_t: 10, closed_t: 20 }];
    custom.trips = { vehicle: [pair.driver_id], state: ["on_trip"], rider: [null],
      t0: [0], t1: [30], dist_m: [30], path: [[0, 0, 30, 30]], ts: [[0, 30]] };
    custom.manifest.time = { start: 0, end: 30 };
    const d = new ReplayDisplay(new Replay(custom)), batches = d.pathBatches();
    const shared = batches[d.stateIndex.get("shared")!], trip = batches[d.stateIndex.get("on_trip")!];
    expect(Array.from(shared.timestamps)).toEqual([10, 20]);
    expect(Array.from(shared.positions)).toEqual([10, 10, 20, 20]);
    expect(Array.from(trip.timestamps)).toEqual([0, 10, 20, 30]);
    expect(shared.length).toBe(1); expect(trip.length).toBe(2);
  });

  it("shows booked customers until exact pickup/cancellation and recovers them when seeking backwards", () => {
    for (const r of docs.manifest.shared!.riders) {
      const has = (t: number) => display.waitingAt(t).some(x => x.rider === r.id);
      if (r.booked_t === null) { expect(has(rp.end)).toBe(false); continue; }
      expect(has(r.booked_t - 0.001)).toBe(false);
      const until = Math.min(r.pickup_t ?? Infinity, r.cancel_t ?? Infinity);
      if (until > r.booked_t) {
        expect(has(r.booked_t)).toBe(true);
        expect(has(until - 0.001)).toBe(true);
      }
      expect(has(until)).toBe(false);
      if (until > r.booked_t) expect(has(r.booked_t)).toBe(true);
    }
    expect(new Set(display.requests.map(r => r.preference))).toEqual(new Set(["shared_only", "exclusive_only"]));
  });

  it("toggles Shared and Exclusive request layers independently of vehicle visibility", () => {
    const colors = stateRgb(display.states, "A"), t = rp.start + 1;
    const hidden = Object.fromEntries(display.states.map(s => [s.id, true]));
    for (const preference of ["shared_only", "exclusive_only"] as const) {
      const plan = layerPlan({ states: display.states.map(s => s.id), hidden, mode: "trajectories", elapsed: 1,
        selected: null, showOD: false, showRequests: { [preference]: true } });
      const requests = plan.filter(p => p.kind === "requests");
      expect(requests).toEqual([{ kind: "requests", id: `requests-${preference}`, preference }]);
      const layers = buildLayers(plan, { rp, t, frame: computeFrame(rp, t, display.states.map(() => false), colors, undefined, display),
        batches: display.pathBatches(), colors, stateIndex: display.stateIndex, selected: null,
        od: null, requests: display.waitingAt(t), onPick: () => {}, onHover: () => {} });
      const labels = layers.find(l => l.id === `requests-${preference}-labels`) as TextLayer | undefined;
      expect(labels?.props.getText?.({}, { index: 0, data: [], target: [] })).toBe(preference === "shared_only" ? "S" : "E");
      expect((layers.find(l => l.id === "vehicles")?.props.data as { length: number }).length).toBe(0);
    }
  });

  it("continues displaying legacy exclusive replay without inventing shared pairs", async () => {
    const legacy = new Replay(await loadFolder(join(__dirname, "..", "..", "public", "fixtures", "hanoi_center_demo")));
    const d = new ReplayDisplay(legacy);
    expect(d.states).toBe(legacy.states);
    expect(d.stateIndex.has("shared")).toBe(false);
    expect(d.requests.length).toBeGreaterThan(0);
    expect(d.requests.every(r => r.preference === "exclusive_only")).toBe(true);
    expect(d.pathBatches().map(b => b.length)).toEqual(legacy.pathBatches().map(b => b.length));
  });
});
