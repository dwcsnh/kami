// deck.gl layers from the layer plan (layerPlan.ts) and the frame of the current time.
import { ArcLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { TripsLayer } from "@deck.gl/geo-layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import type { PathBatch, Replay } from "@/data/replay";
import { hexToRgb, type RGB } from "@/design/color";
import { tokens } from "@/design/tokens";
import type { Frame } from "./frame";
import type { PlanItem } from "./layerPlan";

const BRAND = hexToRgb(tokens.color.brand["500"]);
const BRAND_DARK = hexToRgb(tokens.color.brand["700"]);
const WHITE: RGB = [255, 255, 255];
/** In interleaved mode (`?interleaved=1`) trails go below the road labels of the base map; ignored otherwise. */
const BELOW_LABELS = "road-label";

export interface LayerContext {
  rp: Replay;
  t: number;
  frame: Frame;
  batches: PathBatch[];
  colors: RGB[];
  stateIndex: Map<string, number>;
  selected: number | null;
  od: OdIndex | null;
  beforeId?: string;
  interleaved?: boolean;
  onPick: (vehicle: number | null) => void;
  onHover: (info: PickingInfo) => void;
}

export interface OdIndex {
  t: Float64Array;
  from: Float64Array;
  to: Float64Array;
}

export function odIndex(rp: Replay): OdIndex {
  const e = rp.events;
  const idx: number[] = [];
  for (let k = 0; k < e.t.length; k++) if (e.type[k] === "request" && e.to_lon?.[k] != null) idx.push(k);
  const t = new Float64Array(idx.length);
  const from = new Float64Array(idx.length * 2);
  const to = new Float64Array(idx.length * 2);
  idx.forEach((k, i) => {
    t[i] = e.t[k];
    from[2 * i] = e.lon[k];
    from[2 * i + 1] = e.lat[k];
    to[2 * i] = e.to_lon![k] as number;
    to[2 * i + 1] = e.to_lat![k] as number;
  });
  return { t, from, to };
}

function lowerBound(a: Float64Array, x: number): number {
  let lo = 0;
  let hi = a.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    if (a[m] < x) lo = m + 1;
    else hi = m;
  }
  return lo;
}

export function buildLayers(plan: PlanItem[], ctx: LayerContext): Layer[] {
  const { rp, t, frame, batches, colors, stateIndex } = ctx;
  const elapsed = t - rp.start;
  const layers: Layer[] = [];
  for (const item of plan) {
    if (item.kind === "trail") {
      const st = stateIndex.get(item.state);
      if (st === undefined) continue;
      const b = batches[st];
      layers.push(new TripsLayer({
        id: item.id,
        data: { length: b.length, startIndices: b.startIndices,
                attributes: { getPath: { value: b.positions, size: 2 }, getTimestamps: { value: b.timestamps, size: 1 } } },
        _pathType: "open",
        getColor: colors[st],
        widthUnits: "meters",
        getWidth: item.emphasis ? 9 : 6,
        widthMinPixels: item.emphasis ? 2 : 1.5,
        widthMaxPixels: item.emphasis ? 7 : 5,
        capRounded: true,
        jointRounded: true,
        opacity: item.opacity,
        fadeTrail: item.fade,
        trailLength: item.trailLength,
        currentTime: elapsed,
        ...(ctx.interleaved ? { beforeId: ctx.beforeId ?? BELOW_LABELS } : {}),
        parameters: { depthWriteEnabled: false },
      } as never));
    } else if (item.kind === "od" && ctx.od) {
      const od = ctx.od;
      const half = item.windowS / 2;
      const a = lowerBound(od.t, t - half);
      const z = lowerBound(od.t, t + half);
      const n = Math.max(0, z - a);
      const pickupColor = colors[stateIndex.get("pickup") ?? 0];
      const tripColor = colors[stateIndex.get("on_trip") ?? 0];
      layers.push(new ArcLayer({
        id: "od",
        data: { length: n, attributes: {
          getSourcePosition: { value: od.from.subarray(2 * a, 2 * z), size: 2 },
          getTargetPosition: { value: od.to.subarray(2 * a, 2 * z), size: 2 },
        } },
        getSourceColor: [...pickupColor, 170],
        getTargetColor: [...tripColor, 170],
        getWidth: 1.5,
        getHeight: 0.35,
        greatCircle: false,
        ...(ctx.interleaved ? { beforeId: ctx.beforeId ?? BELOW_LABELS } : {}),
        updateTriggers: { getSourcePosition: [a, z], getTargetPosition: [a, z] },
      } as never));
    } else if (item.kind === "selected" && ctx.selected !== null) {
      const seg = rp.segmentAt(ctx.selected, t);
      const paths: { path: [number, number][]; color: [number, number, number, number]; width: number }[] = [];
      if (seg >= 0) {
        if (rp.segLen[seg] > 1) paths.push({ path: rp.segmentPath(seg), color: [...BRAND_DARK, 230], width: 10 });
        const nx = rp.nextMoving(seg);
        if (nx >= 0) paths.push({ path: rp.segmentPath(nx), color: [...BRAND, 150], width: 8 });
      }
      layers.push(new PathLayer({
        id: "selected-route",
        data: paths,
        getPath: (d: (typeof paths)[number]) => d.path,
        getColor: (d: (typeof paths)[number]) => d.color,
        getWidth: (d: (typeof paths)[number]) => d.width,
        widthUnits: "meters",
        widthMinPixels: 3,
        widthMaxPixels: 9,
        capRounded: true,
        jointRounded: true,
        ...(ctx.interleaved ? { beforeId: ctx.beforeId ?? BELOW_LABELS } : {}),
        updateTriggers: { getPath: [ctx.selected, seg] },
      } as never));
      const pos = rp.positionAt(ctx.selected, t);
      if (pos) {
        layers.push(new ScatterplotLayer({
          id: "selected-halo",
          data: [pos],
          getPosition: (d: [number, number]) => d,
          radiusUnits: "pixels",
          getRadius: 15,
          filled: true,
          getFillColor: [...BRAND, 60],
          stroked: true,
          getLineColor: [...BRAND_DARK, 255],
          lineWidthUnits: "pixels",
          getLineWidth: 2,
          updateTriggers: { getPosition: t },
        } as never));
      }
    } else if (item.kind === "vehicles") {
      layers.push(new ScatterplotLayer({
        id: "vehicles",
        data: { length: frame.length, attributes: {
          getPosition: { value: frame.positions, size: 2 },
          getFillColor: { value: frame.colors, size: 4, normalized: true },
        } },
        billboard: true,                 // round dots also when the map is tilted
        radiusUnits: "meters",
        getRadius: 16 * item.radiusScale,
        radiusMinPixels: 3.5 * item.radiusScale,
        radiusMaxPixels: 9,
        stroked: true,
        getLineColor: WHITE,
        lineWidthUnits: "pixels",
        getLineWidth: 1.5,
        pickable: true,
        autoHighlight: true,
        highlightColor: [...BRAND, 255],
        onClick: (info: PickingInfo) => {
          ctx.onPick(info.index >= 0 ? frame.vehicle[info.index] : null);
          return true;
        },
        onHover: ctx.onHover,
        updateTriggers: { getPosition: t, getFillColor: t },
      } as never));
    }
  }
  return layers;
}
