"use client";
// Mapbox GL base map + deck.gl overlay (interleaved). Layers are rebuilt imperatively when the clock or the
// display settings change — React does not re-render on every frame.
import "mapbox-gl/dist/mapbox-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import type { PickingInfo } from "@deck.gl/core";
import mapboxgl from "mapbox-gl";
import { useEffect, useRef } from "react";
import type { Replay } from "@/data/replay";
import type { RGB } from "@/design/color";
import { usePlayback } from "@/store/playback";
import { MAX_PITCH, MAX_ZOOM, MIN_ZOOM, PITCH_3D, STYLE_URL, tuneBaseStyle } from "./baseStyle";
import { computeFrame, type Frame } from "./frame";
import { layerPlan } from "./layerPlan";
import { buildLayers, odIndex } from "./layers";
import { useFrameStore } from "./frameStore";

export interface MapApi {
  fitArea(): void;
  setPitch(deg: number): void;
  getPitch(): number;
  getBearing(): number;
  zoomBy(delta: number): void;
  resetNorth(): void;
  map: mapboxgl.Map;
}

export const mapApiRef: { current: MapApi | null } = { current: null };

function areaBounds(rp: Replay): mapboxgl.LngLatBoundsLike {
  const b = rp.manifest.area?.bbox ?? rp.manifest.bounds ?? [105.8, 21.0, 105.87, 21.05];
  return [[b[0], b[1]], [b[2], b[3]]];
}

/** `?view=lon,lat,zoom[,pitch[,bearing]]` opens the map there instead of fitting the area. */
function viewFromUrl(): { center: [number, number]; zoom: number; pitch: number; bearing: number } | null {
  const v = new URLSearchParams(window.location.search).get("view");
  const n = v?.split(",").map(Number) ?? [];
  if (n.length < 3 || n.some((x) => !Number.isFinite(x))) return null;
  return { center: [n[0], n[1]], zoom: n[2], pitch: n[3] ?? 0, bearing: n[4] ?? 0 };
}

export function MapView({ replay, token, colors }: { replay: Replay; token: string; colors: RGB[] }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    mapboxgl.accessToken = token;
    const rp = replay;
    // keep the area clear of the floating panels (left column, metrics panel, playback bar)
    const fitPadding = () => {
      const w = container.current?.clientWidth ?? 1280;
      const h = container.current?.clientHeight ?? 800;
      const right = usePlayback.getState().panelOpen ? Math.min(420, w * 0.3) : 80;
      return { top: Math.min(40, h * 0.05), bottom: Math.min(110, h * 0.15), left: Math.min(310, w * 0.25), right };
    };
    const view = viewFromUrl();
    const map = new mapboxgl.Map({
      container: container.current,
      style: STYLE_URL,
      ...(view ?? { bounds: areaBounds(rp), fitBoundsOptions: { padding: fitPadding() } }),
      minZoom: MIN_ZOOM,
      maxZoom: MAX_ZOOM,
      maxPitch: MAX_PITCH,
      antialias: true,
      projection: "mercator",
      attributionControl: true,
    });
    map.addControl(new mapboxgl.ScaleControl({ unit: "metric", maxWidth: 110 }), "bottom-right");
    map.keyboard.enable();

    // deck.gl draws in its own canvas above the map (not interleaved): a frame of moving vehicles then does not
    // force Mapbox to redraw every tile — 49 → 270 fps median at zoom 16 tilted 60° on the integrated GPU (AC03-6).
    // `?interleaved=1` puts the layers inside the map (trails below the street labels) for comparison.
    const interleaved = new URLSearchParams(window.location.search).get("interleaved") === "1";
    const overlay = new MapboxOverlay({ interleaved, layers: [] });
    map.addControl(overlay as unknown as mapboxgl.IControl);

    const batches = rp.pathBatches();
    const od = odIndex(rp);
    const stateIds = rp.states.map((s) => s.id);
    let frame: Frame | undefined;
    let beforeId: string | undefined;
    let raf = 0;

    const onHover = (info: PickingInfo) => {
      map.getCanvas().style.cursor = info.index >= 0 ? "pointer" : "";
    };
    const onPick = (vi: number | null) => usePlayback.getState().select(vi);

    const render = () => {
      raf = 0;
      const s = usePlayback.getState();
      const visible = stateIds.map((id) => !s.hidden[id]);
      frame = computeFrame(rp, s.t, visible, colors, frame);
      useFrameStore.getState().publish(frame.counts, frame.online, s.t);
      const plan = layerPlan({ states: stateIds, hidden: s.hidden, mode: s.mode, elapsed: s.t - rp.start,
                               selected: s.selected, showOD: s.showOD });
      overlay.setProps({ layers: buildLayers(plan, { rp, t: s.t, frame, batches, colors, stateIndex: rp.stateIndex,
                                                     selected: s.selected, od, beforeId, interleaved, onPick, onHover }) });
      if (s.follow && s.selected !== null) {
        const p = rp.positionAt(s.selected, s.t);
        if (p) map.jumpTo({ center: p as [number, number] });
      }
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(render);
    };

    map.on("idle", () => {
      (window as unknown as { __kamiMapIdle?: boolean }).__kamiMapIdle = true;
    });
    map.on("style.load", () => {
      tuneBaseStyle(map);
      const layers = map.getStyle()?.layers ?? [];
      beforeId = layers.find((l) => /road-label/.test(l.id))?.id ?? layers.find((l) => l.type === "symbol")?.id;
      schedule();
    });
    map.on("click", (e) => {
      const picked = overlay.pickObject({ x: e.point.x, y: e.point.y, radius: 6 });
      if (!picked) usePlayback.getState().select(null);
    });
    map.on("dragstart", () => {
      if (usePlayback.getState().follow) usePlayback.getState().setFollow(false);
    });

    const unsub = usePlayback.subscribe(schedule);
    mapApiRef.current = {
      map,
      fitArea: () => map.fitBounds(areaBounds(rp), { padding: fitPadding(), pitch: 0, bearing: 0, duration: 800 }),
      setPitch: (deg) => map.easeTo({ pitch: deg, duration: 600 }),
      getPitch: () => map.getPitch(),
      getBearing: () => map.getBearing(),
      zoomBy: (delta) => map.easeTo({ zoom: map.getZoom() + delta, duration: 300 }),
      resetNorth: () => map.easeTo({ bearing: 0, pitch: 0, duration: 500 }),
    };
    (window as unknown as { __kamiMap?: mapboxgl.Map }).__kamiMap = map;
    return () => {
      unsub();
      if (raf) cancelAnimationFrame(raf);
      mapApiRef.current = null;
      map.remove();
    };
  }, [replay, token, colors]);

  return <div ref={container} style={{ position: "absolute", inset: 0 }} data-testid="map" />;
}

export { PITCH_3D };
