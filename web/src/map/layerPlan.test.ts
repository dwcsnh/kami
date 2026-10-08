// AC03-4: state toggles and the "moving vehicles" ↔ "trajectories" mode.
import { describe, expect, it } from "vitest";
import { TRAIL_S, layerPlan } from "./layerPlan";

const STATES = ["idle", "cruising", "pickup", "on_trip", "reposition"];
const base = { states: STATES, hidden: {}, mode: "vehicles" as const, elapsed: 1200, selected: null, showOD: false };

describe("layerPlan", () => {
  it("one fading short trail per moving state (on_trip at the bottom), then the vehicles", () => {
    const p = layerPlan(base);
    const trails = p.filter((x) => x.kind === "trail");
    expect(trails.map((x) => x.id)).toEqual(["trail-on_trip", "trail-cruising", "trail-pickup", "trail-reposition"]);
    for (const t of trails) {
      expect(t.trailLength).toBe(TRAIL_S);
      expect(t.fade).toBe(true);
    }
    expect(p.at(-1)).toMatchObject({ kind: "vehicles", states: STATES });
  });

  it("hiding a state removes its trail and its vehicles", () => {
    const p = layerPlan({ ...base, hidden: { cruising: true, idle: true } });
    expect(p.some((x) => x.id === "trail-cruising")).toBe(false);
    const v = p.find((x) => x.kind === "vehicles");
    expect(v && v.kind === "vehicles" && v.states).toEqual(["pickup", "on_trip", "reposition"]);
  });

  it("trajectory mode accumulates everything driven so far, without fading", () => {
    const p = layerPlan({ ...base, mode: "trajectories" });
    for (const t of p) if (t.kind === "trail") {
      expect(t.trailLength).toBeGreaterThan(1200);
      expect(t.fade).toBe(false);
    }
    const back = layerPlan({ ...base, mode: "vehicles" });
    expect(back.filter((x) => x.kind === "trail").every((t) => t.kind === "trail" && t.trailLength === TRAIL_S)).toBe(true);
  });

  it("selection and OD layers", () => {
    const p = layerPlan({ ...base, selected: 3, showOD: true });
    expect(p.map((x) => x.kind)).toContain("selected");
    expect(p.map((x) => x.kind)).toContain("od");
    expect(p.at(-1)!.kind).toBe("vehicles");
  });

  it("all states hidden: no trails, no vehicles shown", () => {
    const hidden = Object.fromEntries(STATES.map((s) => [s, true]));
    const p = layerPlan({ ...base, hidden });
    expect(p.filter((x) => x.kind === "trail")).toHaveLength(0);
    const v = p.find((x) => x.kind === "vehicles");
    expect(v && v.kind === "vehicles" && v.states).toEqual([]);
  });
});
