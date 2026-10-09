import type { MetricRow, Progress, RunStatus } from "./types";
export const MAX_LIVE_ROWS = 2000;
export interface LiveState { runId: number | null; rows: MetricRow[]; gap: boolean; trimmed: boolean; progress: Progress; status?: RunStatus }
export const emptyLive = (runId: number | null = null): LiveState => ({ runId, rows: [], gap: false, trimmed: false, progress: {} });
export function acceptFrame(state: LiveState, kind: string, data: unknown): LiveState {
  const d = data as { run_id?: number; row?: MetricRow; progress?: Progress; status?: RunStatus } & Progress;
  if (!d || typeof d !== "object" || (d.run_id !== undefined && d.run_id !== state.runId)) return state;
  if (kind === "resync") return { ...state, gap: true };
  if (kind === "progress") return { ...state, progress: d };
  if (kind === "status") return { ...state, progress: d.progress ?? {}, status: d.status };
  if (kind === "terminal") return { ...state, status: d.status };
  if (kind !== "metric" || !d.row || !Number.isFinite(d.row.t)) return state;
  const row = d.row;
  const rows = state.rows.filter(x => x.t !== row.t).concat(row).sort((a,b) => a.t-b.t);
  return { ...state, rows: rows.slice(-MAX_LIVE_ROWS), trimmed: state.trimmed || rows.length > MAX_LIVE_ROWS };
}
export function visibleMetric(name: string): boolean {
  return !name.startsWith("rider.pool_") && !name.startsWith("rider.pooled_") &&
    !["rider.detour_ratio", "platform.pooled_jobs", "platform.surcharge_total"].includes(name);
}
export async function startQueued(queue: () => Promise<{ id: number }>, start: (id: number) => Promise<unknown>, existing?: number, retain?: (id: number) => void) {
  const id = existing ?? (await queue()).id;
  retain?.(id); // A failed start retains the immutable queued snapshot, avoiding duplicate runs.
  await start(id);
  return id;
}
