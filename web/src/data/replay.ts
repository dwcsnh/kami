// In-memory replay: typed arrays built once from the JSON documents, and the look-ups every frame needs.
// Rules (same as kami/replay/query.py, checked against its samples in replay.test.ts):
//  • segment at t: the vehicle's segment with t0 ≤ t < t1 (its last segment also at t = t1);
//  • position: linear interpolation between the two points around t, clamped to the first / last point;
//  • metrics at t: the last time-series row with t_row ≤ t (snapshot definition of the engine, S01-6).
import type { EventsDoc, Manifest, MetricsDoc, ReplayDocs, StateDef, VehicleRow } from "./types";

export interface RiderTrip {
  rider: number;
  request?: number;
  matched?: number;
  eta?: number;          // promised pick-up time
  pickup?: number;
  dropoff?: number;
  cancel?: number;
  origin?: [number, number];
  dest?: [number, number];
}

/** Per-state binary data for deck.gl path layers (TripsLayer / PathLayer). */
export interface PathBatch {
  length: number;               // number of paths
  startIndices: Uint32Array;    // first vertex of every path
  positions: Float64Array;      // [x, y] per vertex
  timestamps: Float32Array;     // seconds since replay start, per vertex
  segments: Uint32Array;        // segment index of every path
}

export class Replay {
  readonly manifest: Manifest;
  readonly vehicles: VehicleRow[];
  readonly states: StateDef[];
  readonly stateIndex = new Map<string, number>();
  readonly vehicleIndex = new Map<number, number>();
  readonly start: number;
  readonly end: number;
  readonly metrics: MetricsDoc;
  readonly events: EventsDoc;

  // segments (sorted by vehicle, t0)
  readonly segVehicle: Int32Array;
  readonly segState: Uint8Array;
  readonly segRider: Int32Array;
  readonly segT0: Float64Array;
  readonly segT1: Float64Array;
  readonly segDist: Float64Array;
  readonly segStart: Uint32Array;
  readonly segLen: Uint32Array;
  // points
  readonly pos: Float64Array;
  readonly pts: Float64Array;
  // vehicles → segments
  readonly vehStart: Uint32Array;
  readonly vehCount: Uint32Array;
  /** Cumulative distance (m) driven by the vehicle before each segment. */
  readonly segDistBefore: Float64Array;

  private readonly riders = new Map<number, RiderTrip>();

  constructor(docs: ReplayDocs) {
    const { manifest, trips } = docs;
    this.manifest = manifest;
    this.vehicles = docs.vehicles;
    this.states = manifest.states;
    this.states.forEach((s, i) => this.stateIndex.set(s.id, i));
    this.vehicles.forEach((v, i) => this.vehicleIndex.set(v.id, i));
    this.start = manifest.time.start;
    this.end = manifest.time.end;
    this.metrics = docs.metrics;
    this.events = docs.events;

    const n = trips.vehicle.length;
    this.segVehicle = new Int32Array(n);
    this.segState = new Uint8Array(n);
    this.segRider = new Int32Array(n);
    this.segT0 = new Float64Array(n);
    this.segT1 = new Float64Array(n);
    this.segDist = new Float64Array(n);
    this.segStart = new Uint32Array(n);
    this.segLen = new Uint32Array(n);
    this.segDistBefore = new Float64Array(n);
    let nPts = 0;
    for (let i = 0; i < n; i++) nPts += trips.ts[i].length;
    this.pos = new Float64Array(nPts * 2);
    this.pts = new Float64Array(nPts);
    this.vehStart = new Uint32Array(this.vehicles.length);
    this.vehCount = new Uint32Array(this.vehicles.length);

    let p = 0;
    let prevV = -1;
    let acc = 0;
    for (let i = 0; i < n; i++) {
      const vi = this.vehicleIndex.get(trips.vehicle[i]);
      if (vi === undefined) throw new Error(`trips.json: unknown vehicle ${trips.vehicle[i]}`);
      const st = this.stateIndex.get(trips.state[i]);
      this.segVehicle[i] = vi;
      this.segState[i] = st ?? 0;
      this.segRider[i] = trips.rider[i] ?? -1;
      this.segT0[i] = trips.t0[i];
      this.segT1[i] = trips.t1[i];
      this.segDist[i] = trips.dist_m[i] ?? 0;
      if (vi !== prevV) {
        this.vehStart[vi] = i;
        acc = 0;
        prevV = vi;
      }
      this.vehCount[vi]++;
      this.segDistBefore[i] = acc;
      acc += this.segDist[i];
      const path = trips.path[i];
      const ts = trips.ts[i];
      this.segStart[i] = p;
      this.segLen[i] = ts.length;
      for (let k = 0; k < ts.length; k++) {
        this.pos[2 * (p + k)] = path[2 * k];
        this.pos[2 * (p + k) + 1] = path[2 * k + 1];
        this.pts[p + k] = ts[k];
      }
      p += ts.length;
    }
    this.indexRiders();
  }

  get segmentCount(): number {
    return this.segVehicle.length;
  }

  // ------------------------------------------------------------------ look-ups
  /** Segment of vehicle index `vi` at `t`, or -1 (offline). */
  segmentAt(vi: number, t: number): number {
    const count = this.vehCount[vi];
    if (!count) return -1;
    const s0 = this.vehStart[vi];
    let lo = 0;
    let hi = count - 1;
    if (t < this.segT0[s0]) return -1;
    while (lo < hi) {                       // last k with t0[k] ≤ t
      const mid = (lo + hi + 1) >> 1;
      if (this.segT0[s0 + mid] <= t) lo = mid;
      else hi = mid - 1;
    }
    const i = s0 + lo;
    if (t < this.segT1[i] || (lo === count - 1 && t === this.segT1[i])) return i;
    return -1;
  }

  stateAt(vi: number, t: number): number {
    const i = this.segmentAt(vi, t);
    return i < 0 ? -1 : this.segState[i];
  }

  /** Writes the position of segment `i` at `t` into `out[o]`, `out[o + 1]`; returns the point index before `t`. */
  positionInSegment(i: number, t: number, out: Float64Array | number[], o = 0): number {
    const s = this.segStart[i];
    const n = this.segLen[i];
    const pts = this.pts;
    const pos = this.pos;
    if (n === 1 || t <= pts[s]) {
      out[o] = pos[2 * s];
      out[o + 1] = pos[2 * s + 1];
      return 0;
    }
    if (t >= pts[s + n - 1]) {
      out[o] = pos[2 * (s + n - 1)];
      out[o + 1] = pos[2 * (s + n - 1) + 1];
      return n - 1;
    }
    let lo = 0;
    let hi = n - 1;
    while (hi - lo > 1) {                   // pts[lo] ≤ t < pts[hi]
      const mid = (lo + hi) >> 1;
      if (pts[s + mid] <= t) lo = mid;
      else hi = mid;
    }
    const a = s + lo;
    const ta = pts[a];
    const tb = pts[a + 1];
    const f = tb > ta ? (t - ta) / (tb - ta) : 0;
    out[o] = pos[2 * a] + (pos[2 * a + 2] - pos[2 * a]) * f;
    out[o + 1] = pos[2 * a + 1] + (pos[2 * a + 3] - pos[2 * a + 1]) * f;
    return lo;
  }

  positionAt(vi: number, t: number): [number, number] | null {
    const i = this.segmentAt(vi, t);
    if (i < 0) return null;
    const out: [number, number] = [0, 0];
    this.positionInSegment(i, t, out);
    return out;
  }

  /** Heading (radians, counter-clockwise from east, in lon/lat space scaled by cos(lat)) at `t`, or null. */
  headingAt(i: number, t: number): number | null {
    const s = this.segStart[i];
    const n = this.segLen[i];
    if (n < 2) return null;
    const out = [0, 0];
    const k = Math.min(this.positionInSegment(i, t, out), n - 2);
    const a = s + k;
    const kx = this.manifest.coords === "lonlat" ? Math.cos((this.pos[2 * a + 1] * Math.PI) / 180) : 1;
    const dx = (this.pos[2 * a + 2] - this.pos[2 * a]) * kx;
    const dy = this.pos[2 * a + 3] - this.pos[2 * a + 1];
    return dx === 0 && dy === 0 ? null : Math.atan2(dy, dx);
  }

  /** Distance (m) driven by vehicle index `vi` from the start of its shift until `t`. */
  distanceAt(vi: number, t: number): number {
    const i = this.segmentAt(vi, t);
    if (i < 0) {
      if (!this.vehCount[vi] || t < this.segT0[this.vehStart[vi]]) return 0;
      const last = this.vehStart[vi] + this.vehCount[vi] - 1;
      return this.segDistBefore[last] + this.segDist[last];
    }
    const s = this.segStart[i];
    const n = this.segLen[i];
    if (n < 2 || this.segDist[i] === 0) return this.segDistBefore[i];
    // share of the (simplified) polyline length covered at t
    const out = [0, 0];
    const k = this.positionInSegment(i, t, out);
    const kx = this.manifest.coords === "lonlat" ? Math.cos((this.pos[2 * s + 1] * Math.PI) / 180) : 1;
    let total = 0;
    let done = 0;
    for (let j = 0; j < n - 1; j++) {
      const a = s + j;
      const d = Math.hypot((this.pos[2 * a + 2] - this.pos[2 * a]) * kx, this.pos[2 * a + 3] - this.pos[2 * a + 1]);
      total += d;
      if (j < k) done += d;
      else if (j === k) done += Math.hypot((out[0] - this.pos[2 * a]) * kx, out[1] - this.pos[2 * a + 1]);
    }
    return this.segDistBefore[i] + (total > 0 ? (this.segDist[i] * done) / total : 0);
  }

  /** Next moving segment of the same vehicle after segment `i` (−1 if none). */
  nextMoving(i: number): number {
    const vi = this.segVehicle[i];
    const last = this.vehStart[vi] + this.vehCount[vi] - 1;
    for (let j = i + 1; j <= last; j++) if (this.segLen[j] > 1) return j;
    return -1;
  }

  // ------------------------------------------------------------------ metrics
  /** Index of the last time-series row with t_row ≤ t, or −1. */
  metricsRowAt(t: number): number {
    const ts = this.metrics.t;
    let lo = 0;
    let hi = ts.length - 1;
    if (!ts.length || t < ts[0]) return -1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (ts[mid] <= t) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  }

  metricsAt(t: number): Record<string, number | null> | null {
    const r = this.metricsRowAt(t);
    if (r < 0) return null;
    const out: Record<string, number | null> = { t: this.metrics.t[r] };
    for (const [k, col] of Object.entries(this.metrics.series)) out[k] = col[r];
    return out;
  }

  /** Vehicles per state at each time (for the state-share chart); index [k][state]. */
  stateCounts(times: number[]): Uint32Array[] {
    return times.map((t) => {
      const c = new Uint32Array(this.states.length);
      for (let vi = 0; vi < this.vehicles.length; vi++) {
        const s = this.stateAt(vi, t);
        if (s >= 0) c[s]++;
      }
      return c;
    });
  }

  // ------------------------------------------------------------------ batches for the map
  /** Moving segments (≥ 2 points) grouped by state, as binary path data. */
  pathBatches(): PathBatch[] {
    const out: PathBatch[] = [];
    for (let st = 0; st < this.states.length; st++) {
      let nPaths = 0;
      let nVerts = 0;
      for (let i = 0; i < this.segmentCount; i++) {
        if (this.segState[i] === st && this.segLen[i] > 1) {
          nPaths++;
          nVerts += this.segLen[i];
        }
      }
      const startIndices = new Uint32Array(nPaths);
      const segments = new Uint32Array(nPaths);
      const positions = new Float64Array(nVerts * 2);
      const timestamps = new Float32Array(nVerts);
      let p = 0;
      let v = 0;
      for (let i = 0; i < this.segmentCount; i++) {
        if (this.segState[i] !== st || this.segLen[i] < 2) continue;
        startIndices[p] = v;
        segments[p] = i;
        const s = this.segStart[i];
        for (let k = 0; k < this.segLen[i]; k++) {
          positions[2 * v] = this.pos[2 * (s + k)];
          positions[2 * v + 1] = this.pos[2 * (s + k) + 1];
          timestamps[v] = this.pts[s + k] - this.start;
          v++;
        }
        p++;
      }
      out.push({ length: nPaths, startIndices, positions, timestamps, segments });
    }
    return out;
  }

  /** Polyline of segment `i` as [[x, y], …] (selected-vehicle highlight). */
  segmentPath(i: number): [number, number][] {
    const s = this.segStart[i];
    const out: [number, number][] = [];
    for (let k = 0; k < this.segLen[i]; k++) out.push([this.pos[2 * (s + k)], this.pos[2 * (s + k) + 1]]);
    return out;
  }

  // ------------------------------------------------------------------ riders
  private indexRiders(): void {
    const e = this.events;
    for (let k = 0; k < e.t.length; k++) {
      const id = e.rider[k];
      let r = this.riders.get(id);
      if (!r) this.riders.set(id, (r = { rider: id }));
      const t = e.t[k];
      switch (e.type[k]) {
        case "request":
          r.request = t;
          r.origin = [e.lon[k], e.lat[k]];
          if (e.to_lon?.[k] != null && e.to_lat?.[k] != null) r.dest = [e.to_lon[k] as number, e.to_lat[k] as number];
          break;
        case "matched":
          r.matched = t;
          if (e.eta?.[k] != null) r.eta = e.eta[k] as number;
          break;
        case "pickup":
          r.pickup = t;
          break;
        case "dropoff":
          r.dropoff = t;
          break;
        case "cancel":
          r.cancel = t;
          break;
      }
    }
  }

  rider(id: number): RiderTrip | undefined {
    return this.riders.get(id);
  }
}

/** Completed / cancelled per bucket from the window counters of the time series, up to `t`. */
export function bucketCounts(m: MetricsDoc, bucketS: number, upTo = Infinity): { start: number[]; completed: number[]; cancelled: number[] } {
  const iv = m.interval_s ?? (m.t.length > 1 ? m.t[1] - m.t[0] : 60);
  const done = m.series["rider.completed"] ?? [];
  const canc = m.series["rider.cancelled"] ?? [];
  const map = new Map<number, [number, number]>();
  // row k counts the window [t_k − Δ, t_k); the first row (t_0 = start) has an empty window
  const first = m.t.length ? Math.floor(m.t[0] / bucketS) * bucketS : 0;
  for (let k = 0; k < m.t.length; k++) {
    if (m.t[k] > upTo) break;
    const b = Math.max(first, Math.floor((m.t[k] - iv) / bucketS) * bucketS);
    const cur = map.get(b) ?? [0, 0];
    cur[0] += done[k] ?? 0;
    cur[1] += canc[k] ?? 0;
    map.set(b, cur);
  }
  const start = [...map.keys()].sort((a, b) => a - b);
  return { start, completed: start.map((b) => map.get(b)![0]), cancelled: start.map((b) => map.get(b)![1]) };
}

export function formatClock(t: number, withSeconds = true): string {
  const s = Math.max(0, Math.floor(t));
  const h = Math.floor(s / 3600) % 24;
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const p = (x: number) => String(x).padStart(2, "0");
  return withSeconds ? `${p(h)}:${p(m)}:${p(sec)}` : `${p(h)}:${p(m)}`;
}
