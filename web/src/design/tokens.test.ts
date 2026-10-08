// AC03-7: light-mode text contrast (WCAG AA) and a distinguishable vehicle-state palette.
import { describe, expect, it } from "vitest";
import { contrast, deltaE } from "./color";
import tokens from "./tokens.json";

type Flat = Record<string, string>;
const color = tokens.color as unknown as Flat & { state: Record<string, Record<string, string>> };

describe("design tokens", () => {
  it("Tiffany is the brand accent", () => {
    expect(tokens.color.brand["500"]).toBe("#0ABAB5");
    expect(color.accent).toBe("#0ABAB5");
  });

  for (const [fg, bg, min] of tokens.contrast.text as [string, string, number][]) {
    it(`text ${fg} on ${bg} ≥ ${min}:1`, () => {
      expect(contrast(color[fg], color[bg])).toBeGreaterThanOrEqual(min);
    });
  }
  for (const [fg, bg, min] of tokens.contrast.graphics as [string, string, number][]) {
    it(`graphic ${fg} on ${bg} ≥ ${min}:1`, () => {
      expect(contrast(color[fg], color[bg])).toBeGreaterThanOrEqual(min);
    });
  }

  for (const [name, palette] of Object.entries(color.state)) {
    describe(`state palette ${name}`, () => {
      const entries = Object.entries(palette);
      for (const [state, hex] of entries) {
        it(`${state} ≥ 3:1 against the map ground and the panel surface`, () => {
          expect(contrast(hex, color["map-ground"])).toBeGreaterThanOrEqual(3);
          expect(contrast(hex, color.surface)).toBeGreaterThanOrEqual(3);
        });
        it(`${state} is not confused with Tiffany (ΔE ≥ 20)`, () => {
          expect(deltaE(hex, color.accent)).toBeGreaterThanOrEqual(20);
        });
      }
      it("states differ pairwise (ΔE ≥ 20)", () => {
        for (let i = 0; i < entries.length; i++) {
          for (let j = i + 1; j < entries.length; j++) {
            expect(deltaE(entries[i][1], entries[j][1]), `${entries[i][0]} vs ${entries[j][0]}`).toBeGreaterThanOrEqual(20);
          }
        }
      });
    });
  }
});
