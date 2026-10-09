import type { Replay } from "./replay";
import type { SharedPair } from "./types";

export interface JourneyMark { label: string; t: number; kind: "booked" | "matched" | "pickup" | "dropoff" | "closed" }

export function journeyMarks(rp: Replay, pair: SharedPair): JourneyMark[] {
  const marks: JourneyMark[] = [];
  for (const id of pair.rider_ids) {
    const r = rp.manifest.shared?.riders.find(r => r.id === id);
    if (r?.booked_t != null) marks.push({ label: `Khách #${id} đặt Shared`, t: r.booked_t, kind: "booked" });
  }
  marks.push({ label: "Hệ thống ghép cặp, xe đi đón", t: pair.created_t, kind: "matched" });
  for (const stop of pair.stops) {
    const t = stop.kind === "pickup" ? pair.pickups[stop.rider_id] : pair.dropoffs[stop.rider_id];
    if (t !== undefined) marks.push({ label: `${stop.kind === "pickup" ? "Đón" : "Trả"} khách #${stop.rider_id}`,
      t, kind: stop.kind === "pickup" ? "pickup" : "dropoff" });
  }
  if (pair.closed_t !== null) marks.push({ label: pair.reason ? "Cặp kết thúc: " + pair.reason : "Hoàn tất cặp", t: pair.closed_t, kind: "closed" });
  return marks.sort((a, b) => a.t - b.t);
}

export function journeyStage(rp: Replay, pair: SharedPair, t: number): string {
  const booked = journeyMarks(rp, pair).filter(m => m.kind === "booked");
  if (!booked.some(m => m.t <= t)) return "Chưa có khách đặt";
  if (t < pair.created_t) return `Chờ hệ thống ghép · ${booked.filter(m => m.t <= t).length}/2 khách đã đặt`;
  if (pair.closed_t !== null && t >= pair.closed_t) return pair.reason ? "Cặp đã kết thúc: " + pair.reason : "Đã trả hết khách · Hoàn tất";
  const onboard = rp.sharedOnboardAt(pair.id, t);
  if (onboard.length === 2) return "Hai khách trên xe · Đang đi chung";
  const next = pair.stops.find(s => {
    const actual = s.kind === "pickup" ? pair.pickups[s.rider_id] : pair.dropoffs[s.rider_id];
    return actual !== undefined && t < actual;
  });
  if (next) return `${next.kind === "pickup" ? "Đi đón" : "Đi trả"} khách #${next.rider_id} · ${onboard.length}/2 khách trên xe`;
  return "Cặp đang được phục vụ";
}

export function journeyStart(rp: Replay, pair: SharedPair): number {
  return Math.max(rp.start, Math.min(...journeyMarks(rp, pair).map(m => m.t)) - 1);
}
