export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export interface Ref { ref: number | string }
export interface VehicleType { name: string; group: "bike" | "car"; seats: number; range_km?: number | null; [key: string]: unknown }
export interface Fleet { name: string; composition: { vehicle_type: string; count: number }[]; [key: string]: unknown }
export interface Source { kind: string; preset?: string; overrides?: Record<string, unknown>; t_start?: number; t_end?: number; demand_per_hour?: number; weather?: [number, string][]; incidents?: Record<string, unknown>[]; [key: string]: unknown }
export interface Scenario { name: string; network?: Record<string, unknown>; zones?: Record<string, unknown>; source: Source; seed?: number; [key: string]: unknown }
export interface RunSpec { name: string; scenario: Scenario; fleets?: (Ref | Fleet)[]; vehicle_types?: (Ref | VehicleType)[]; charging_stations?: unknown[]; seed?: number | null; crn_seed?: number | null; sim_config?: Record<string, unknown>; outputs?: Record<string, unknown>; [key: string]: unknown }
export interface Entity<T> { id: number; name: string; spec: T }
export interface RunRow { id: number; name: string; status: RunStatus; seed: number | null; created_at: string; finished_at: string | null; wall_s: number | null; events: number | null }
export interface Progress { phase?: string; fraction?: number | null; eta_s?: number | null; simulation_time?: number | null }
export interface RunDetail extends RunRow { run_spec: RunSpec; source_spec: RunSpec; scenario_id: number | null; provenance: Record<string, unknown>; managed: boolean; progress: Progress; error: string | null; error_code: string | null }
export interface Health { status: string; capabilities: { stage: string; live_metrics: boolean; live_vehicle_snapshots: boolean; ev: boolean; pricing_v2: boolean; shared_ride_versions?: number[] } }
export type MetricRow = { t: number } & Record<string, number | null>;
export interface MetricDelta { metric: string; baseline: number | null; candidate: number | null; delta: number | null; delta_percent: number | null; direction: number; verdict: "better" | "worse" | "equal" | null }
export interface Comparison { baseline_id: number; comparisons: { run_id: number; warnings: string[]; metrics: MetricDelta[] }[] }
export type Resource = "vehicle-types" | "fleets" | "scenarios";
export const statusLabels: Record<RunStatus, string> = { queued: "Chờ bắt đầu", running: "Đang chạy", succeeded: "Hoàn thành", failed: "Thất bại", cancelled: "Đã huỷ" };
export const isTerminal = (s: RunStatus) => s === "succeeded" || s === "failed" || s === "cancelled";
