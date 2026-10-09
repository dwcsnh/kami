import { join } from "node:path";
import { beforeAll, expect, it } from "vitest";
import { Replay } from "./replay";
import { loadFolder } from "./testing";
import { journeyMarks, journeyStage, journeyStart } from "./sharedJourney";

let rp: Replay;
beforeAll(async () => { rp = new Replay(await loadFolder(join(__dirname, "..", "..", "public", "fixtures", "shared_v1_walkthrough"))); });
it("walkthrough shows two real bookings, a wait to match and four distinct moving stops", () => {
  const pair = rp.manifest.shared!.pairs[0], marks = journeyMarks(rp, pair);
  expect(marks.map(m => m.kind)).toEqual(["booked", "booked", "matched", "pickup", "pickup", "dropoff", "dropoff", "closed"]);
  expect(new Set(pair.stops.map(s => s.loc)).size).toBe(4);
  expect(pair.created_t).toBeGreaterThan(marks[1].t);
  const pickups = Object.values(pair.pickups).sort((a,b) => a-b), drops = Object.values(pair.dropoffs).sort((a,b) => a-b);
  expect(pickups[0] - pair.created_t).toBeGreaterThan(30);
  expect(pickups[1] - pickups[0]).toBeGreaterThan(30);
  expect(drops[1] - drops[0]).toBeGreaterThan(30);
  expect(journeyStage(rp, pair, journeyStart(rp, pair))).toBe("Chưa có khách đặt");
  expect(journeyStage(rp, pair, marks[1].t)).toContain("Chờ hệ thống ghép · 2/2");
  expect(journeyStage(rp, pair, pair.created_t)).toContain("Đi đón khách #2 · 0/2");
  expect(journeyStage(rp, pair, pickups[0])).toContain("Đi đón khách #1 · 1/2");
  expect(journeyStage(rp, pair, pickups[1])).toContain("Đang đi chung");
  expect(journeyStage(rp, pair, drops[0])).toContain("Đi trả khách #1 · 1/2");
  expect(journeyStage(rp, pair, pair.closed_t!)).toContain("Hoàn tất");
});
it("the vehicle actually moves between distinct origins, pickups and destinations", () => {
  const pair = rp.manifest.shared!.pairs[0], vi = rp.vehicleIndex.get(pair.driver_id)!;
  const ts = [pair.created_t, ...Object.values(pair.pickups).sort((a,b)=>a-b), ...Object.values(pair.dropoffs).sort((a,b)=>a-b)];
  for(let k=0;k<ts.length-1;k++) {
    expect(rp.positionAt(vi, ts[k])).not.toEqual(rp.positionAt(vi, ts[k+1]));
    expect(rp.distanceAt(vi, ts[k+1]) - rp.distanceAt(vi, ts[k])).toBeGreaterThan(50);
  }
});
