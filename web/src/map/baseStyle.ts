// Mapbox light-v11 tuned at load time (decision D11): quieter base, tinted water, no POI clutter, no 3D buildings.
import type { Map as MapboxMap } from "mapbox-gl";
import { tokens } from "@/design/tokens";

export const STYLE_URL = "mapbox://styles/mapbox/light-v11";
export const MIN_ZOOM = 10;
export const MAX_ZOOM = 18;
export const MAX_PITCH = 60;
export const PITCH_3D = 50;

const HIDE_SYMBOLS = /poi|transit|airport|ferry|natural-point|water-point|settlement-subdivision|road-number|road-exit|aerialway/;

export function tuneBaseStyle(map: MapboxMap): void {
  const style = map.getStyle();
  for (const layer of style?.layers ?? []) {
    const id = layer.id;
    try {
      if (layer.type === "fill-extrusion") {
        map.setLayoutProperty(id, "visibility", "none");                     // no 3D buildings (Q-C)
      } else if (layer.type === "symbol" && HIDE_SYMBOLS.test(id)) {
        map.setLayoutProperty(id, "visibility", "none");
      } else if (layer.type === "symbol" && /road-label|road-name/.test(id)) {
        map.setPaintProperty(id, "text-color", tokens.color.neutral["500"]);
        map.setPaintProperty(id, "text-opacity", 0.85);
      } else if (layer.type === "background" || id === "land") {
        map.setPaintProperty(id, "background-color", tokens.color["map-ground"]);
      } else if (id === "water") {
        map.setPaintProperty(id, "fill-color", tokens.color["map-water"]);
      } else if (layer.type === "fill" && id.startsWith("building")) {
        map.setPaintProperty(id, "fill-opacity", 0.25);
      }
    } catch {
      // a layer of another style version: leave it as is
    }
  }
}
