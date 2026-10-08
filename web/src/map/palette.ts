// Vehicle-state colours from design tokens (two candidate palettes until the user picks one — plan D12 / Q-D).
import { hexToRgb, type RGB } from "@/design/color";
import { tokens } from "@/design/tokens";
import type { StateDef } from "@/data/types";

export type PaletteName = keyof typeof tokens.color.state;
const FALLBACK = tokens.color.neutral["500"];

export function stateHex(states: StateDef[], palette: PaletteName): string[] {
  const p = tokens.color.state[palette] as Record<string, string>;
  return states.map((s) => p[s.id] ?? FALLBACK);
}

export function stateRgb(states: StateDef[], palette: PaletteName): RGB[] {
  return stateHex(states, palette).map(hexToRgb);
}

export function paletteFromUrl(): PaletteName {
  if (typeof window === "undefined") return "A";
  const p = new URLSearchParams(window.location.search).get("palette");
  return p === "B" ? "B" : "A";
}
