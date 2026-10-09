// Which map layers to draw for the current settings (pure, unit-tested — AC03-4). layers.ts turns the plan into
// deck.gl layers.
import type { Mode } from "@/store/playback";
import type { RequestPreference } from "@/data/display";

export const TRAIL_S = 180;                 // "moving vehicles" mode: trail of 3 simulated minutes (decision D13)

export type PlanItem =
  | { kind: "trail"; id: string; state: string; trailLength: number; fade: boolean; opacity: number; emphasis: boolean }
  | { kind: "vehicles"; id: "vehicles"; states: string[]; radiusScale: number }
  | { kind: "selected"; id: "selected" }
  | { kind: "requests"; id: string; preference: RequestPreference }
  | { kind: "pair-stops"; id: "pair-stops" }
  | { kind: "od"; id: "od"; windowS: number };

export interface PlanInput {
  states: string[];
  hidden: Record<string, boolean>;
  mode: Mode;
  elapsed: number;                          // t − replay start (s)
  selected: number | null;
  showOD: boolean;
  showRequests?: Partial<Record<RequestPreference, boolean>>;
  selectedVisible?: boolean;
  focusedPair?: number | null;
}

export function layerPlan({ states, hidden, mode, elapsed, selected, showOD, showRequests, selectedVisible = true, focusedPair }: PlanInput): PlanItem[] {
  const visible = states.filter((s) => !hidden[s]);
  const trajectories = mode === "trajectories";
  // the most common trail (on_trip) goes first, i.e. below the others, so rarer states stay visible on top
  const order = (s: string) => (s === "on_trip" ? 0 : 1);
  const plan: PlanItem[] = visible
    .filter((s) => s !== "idle")             // a parked vehicle draws no trail
    .sort((a, b) => order(a) - order(b))
    .map((state) => ({
      kind: "trail" as const,
      id: `trail-${state}`,
      state,
      trailLength: trajectories ? Math.max(elapsed, 0) + 1 : TRAIL_S,
      fade: !trajectories,
      opacity: trajectories ? 0.4 : 0.9,
      emphasis: state === "on_trip" || state === "shared",
    }));
  if (showOD) plan.push({ kind: "od", id: "od", windowS: 900 });
  if (focusedPair != null) plan.push({ kind: "pair-stops", id: "pair-stops" });
  if (selected !== null && selectedVisible) plan.push({ kind: "selected", id: "selected" });
  for (const preference of ["shared_only", "exclusive_only"] as const) {
    if (showRequests?.[preference]) plan.push({ kind: "requests", id: `requests-${preference}`, preference });
  }
  plan.push({ kind: "vehicles", id: "vehicles", states: visible, radiusScale: trajectories ? 0.7 : 1 });
  return plan;
}
