// kami.replay v1 — the data contract written by `python -m kami replay` (kami/replay/schema.py,
// docs/engine/20-visualizer.md). Readers ignore unknown fields; a newer schema_version is refused.

export const SCHEMA_VERSION = 1;

export interface StateDef {
  id: string;            // "idle" | "cruising" | "pickup" | "on_trip" | "reposition" | later states (Sprint 05)
  label: string;
  color: string;         // token key "state.<id>"
}

export interface FileMeta { path: string; sha256: string; bytes: number; raw_bytes?: number }

export interface Manifest {
  schema_version: number;
  kind: "kami.replay";
  kami_version: string;
  run: { name?: string; scenario?: string; seed?: number; crn_seed?: number | null; policy?: string;
         network?: string; spec_sha256?: string };
  coords: "lonlat" | "xy";
  area: { name: string; bbox: [number, number, number, number]; center?: [number, number]; zoom?: number } | null;
  bounds: [number, number, number, number] | null;
  time: { start: number; end: number; scenario_start?: number };
  states: StateDef[];
  fleets: Record<string, number>;
  counts: { vehicles: number; segments: number; points: number; events: number; metric_rows: number };
  files: Record<"vehicles" | "trips" | "events" | "metrics", FileMeta>;
  simplify: { dist_m: number; dt_s: number };
  shared?: { version: number; fare_factor: number; pairs: SharedPair[]; riders: SharedRider[] };
}

export interface SharedPair {
  id: number; rider_ids: number[]; driver_id: number; created_t: number; closed_t: number | null;
  reason: string | null; stops: { kind: string; rider_id: number; loc: number }[];
  predicted_pickup: Record<string,number>; predicted_dropoff: Record<string,number>;
  pickups: Record<string,number>; dropoffs: Record<string,number>;
  predicted_overlap_s: number; actual_overlap_s: number; actual_shared: boolean;
  overlap_start: number | null; overlap_end: number | null;
}
export interface SharedRider {
  id: number; service_preference: string; pair_history: number[]; fare: number;
  exclusive_reference_fare: number; booked_t: number | null; pickup_deadline: number | null;
  pickup_t: number | null; dropoff_t: number | null; cancel_t: number | null; reason: string | null;
}

export interface VehicleRow {
  id: number;
  fleet: string | null;
  vehicle_type: string | null;
  group: string | null;
  seats: number | null;
  shift: [number, number];
}

export interface TripsDoc {
  vehicle: number[];
  state: string[];
  rider: (number | null)[];
  t0: number[];
  t1: number[];
  dist_m: number[];
  path: number[][];      // flat [x0, y0, x1, y1, …]
  ts: number[][];
}

export type EventType = "request" | "booked" | "declined" | "matched" | "pickup" | "dropoff" | "cancel";

export interface EventsDoc {
  t: number[];
  type: EventType[];
  rider: number[];
  vehicle: (number | null)[];
  lon: number[];
  lat: number[];
  to_lon?: (number | null)[];
  to_lat?: (number | null)[];
  eta?: (number | null)[];
}

export interface MetricsDoc {
  interval_s: number | null;
  t: number[];
  series: Record<string, (number | null)[]>;
}

export interface ReplayDocs {
  manifest: Manifest;
  vehicles: VehicleRow[];
  trips: TripsDoc;
  events: EventsDoc;
  metrics: MetricsDoc;
}
