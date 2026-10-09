// Replay-only display categories. Engine states, metrics and exported files stay authoritative.
import type { PathBatch, Replay } from "./replay";
import type { SharedPair, StateDef } from "./types";

export const SHARED_STATE = "shared";
export type RequestPreference = "shared_only" | "exclusive_only";
export interface WaitingRequest {
  rider: number;
  preference: RequestPreference;
  position: [number, number];
  booked: number;
  until: number;
}

export class ReplayDisplay {
  readonly states: StateDef[];
  readonly stateIndex: Map<string, number>;
  readonly requests: WaitingRequest[] = [];
  private readonly pairs = new Map<number, SharedPair[]>();

  constructor(readonly rp: Replay) {
    this.states = rp.manifest.shared
      ? [...rp.states, { id: SHARED_STATE, label: "Xe share", color: "state.shared" }]
      : rp.states;
    this.stateIndex = new Map(this.states.map((s, i) => [s.id, i]));
    for (const pair of rp.manifest.shared?.pairs ?? []) {
      const vi = rp.vehicleIndex.get(pair.driver_id);
      if (vi === undefined) continue;
      const list = this.pairs.get(vi) ?? [];
      list.push(pair);
      this.pairs.set(vi, list);
    }
    for (const list of this.pairs.values()) list.sort((a, b) => a.created_t - b.created_t);
    const metadata = new Map(rp.manifest.shared?.riders.map(r => [r.id, r]));
    const seen = new Set<number>();
    for (let k = 0; k < rp.events.t.length; k++) {
      if (rp.events.type[k] !== "booked") continue;
      const id = rp.events.rider[k], trip = rp.rider(id), r = metadata.get(id);
      if (seen.has(id) || !trip?.origin) continue;
      seen.add(id);
      // Old exclusive replays have no service-preference metadata.
      const preference = r?.service_preference ?? (rp.manifest.shared ? undefined : "exclusive_only");
      if (preference !== "shared_only" && preference !== "exclusive_only") continue;
      this.requests.push({ rider: id, preference, position: trip.origin,
        booked: r?.booked_t ?? rp.events.t[k],
        until: Math.min(r?.pickup_t ?? trip.pickup ?? Infinity, r?.cancel_t ?? trip.cancel ?? Infinity) });
    }
    this.requests.sort((a, b) => a.booked - b.booked || a.rider - b.rider);
  }

  pairAt(vi: number, t: number): SharedPair | undefined {
    const list = this.pairs.get(vi);
    if (!list?.length) return undefined;
    let lo = 0, hi = list.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (list[mid].created_t <= t) lo = mid + 1; else hi = mid;
    }
    const pair = list[lo - 1];
    return pair && (pair.closed_t === null || t < pair.closed_t) ? pair : undefined;
  }

  stateAt(vi: number, t: number, segment = this.rp.segmentAt(vi, t)): number {
    if (segment < 0) return -1;
    return this.pairAt(vi, t) ? this.stateIndex.get(SHARED_STATE)! : this.rp.segState[segment];
  }

  waitingAt(t: number): WaitingRequest[] {
    let lo = 0, hi = this.requests.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.requests[mid].booked <= t) lo = mid + 1; else hi = mid;
    }
    return this.requests.slice(0, lo).filter(r => t < r.until);
  }

  /** Split paths at pair boundaries so hiding other states never hides shared trails (or vice versa). */
  pathBatches(): PathBatch[] {
    const rp = this.rp;
    if (!rp.manifest.shared) return rp.pathBatches();
    const rows = this.states.map(() => [] as { segment: number; positions: number[]; times: number[] }[]);
    for (let i = 0; i < rp.segmentCount; i++) {
      if (rp.segLen[i] < 2) continue;
      const vi = rp.segVehicle[i], a = rp.segT0[i], z = rp.segT1[i];
      const cuts = new Set([a, z]);
      for (const pair of this.pairs.get(vi) ?? []) {
        if (pair.created_t > a && pair.created_t < z) cuts.add(pair.created_t);
        if (pair.closed_t !== null && pair.closed_t > a && pair.closed_t < z) cuts.add(pair.closed_t);
      }
      const ts = [...cuts].sort((x, y) => x - y);
      for (let c = 0; c < ts.length - 1; c++) {
        const from = ts[c], to = ts[c + 1], positions: number[] = [], times: number[] = [];
        const point = [0, 0];
        rp.positionInSegment(i, from, point); positions.push(...point); times.push(from - rp.start);
        const s = rp.segStart[i];
        for (let k = s; k < s + rp.segLen[i]; k++) {
          if (rp.pts[k] > from && rp.pts[k] < to) {
            positions.push(rp.pos[2 * k], rp.pos[2 * k + 1]); times.push(rp.pts[k] - rp.start);
          }
        }
        rp.positionInSegment(i, to, point); positions.push(...point); times.push(to - rp.start);
        rows[this.stateAt(vi, (from + to) / 2, i)].push({ segment: i, positions, times });
      }
    }
    return rows.map(paths => {
      const n = paths.reduce((sum, p) => sum + p.times.length, 0);
      const batch: PathBatch = { length: paths.length, startIndices: new Uint32Array(paths.length),
        segments: new Uint32Array(paths.length), positions: new Float64Array(2 * n), timestamps: new Float32Array(n) };
      let v = 0;
      paths.forEach((p, k) => {
        batch.startIndices[k] = v; batch.segments[k] = p.segment;
        batch.positions.set(p.positions, 2 * v); batch.timestamps.set(p.times, v); v += p.times.length;
      });
      return batch;
    });
  }
}
