// Vehicle positions at time t (computed on the CPU every frame — decision D13) as binary attributes for deck.gl.
import type { Replay } from "@/data/replay";
import type { RGB } from "@/design/color";

export interface Frame {
  length: number;                // vehicles drawn
  positions: Float64Array;       // [x, y] per drawn vehicle
  colors: Uint8Array;            // RGBA per drawn vehicle
  vehicle: Int32Array;           // vehicle index per drawn vehicle
  counts: Uint32Array;           // vehicles per state (all online vehicles, visible or not)
  online: number;
}

export function computeFrame(rp: Replay, t: number, visible: boolean[], colors: RGB[], prev?: Frame): Frame {
  const n = rp.vehicles.length;
  const f: Frame = prev && prev.vehicle.length === n ? prev : {
    length: 0, positions: new Float64Array(2 * n), colors: new Uint8Array(4 * n), vehicle: new Int32Array(n),
    counts: new Uint32Array(rp.states.length), online: 0,
  };
  f.counts.fill(0);
  let k = 0;
  let online = 0;
  for (let vi = 0; vi < n; vi++) {
    const i = rp.segmentAt(vi, t);
    if (i < 0) continue;
    const st = rp.segState[i];
    f.counts[st]++;
    online++;
    if (!visible[st]) continue;
    rp.positionInSegment(i, t, f.positions, 2 * k);
    const c = colors[st];
    f.colors[4 * k] = c[0];
    f.colors[4 * k + 1] = c[1];
    f.colors[4 * k + 2] = c[2];
    f.colors[4 * k + 3] = 255;
    f.vehicle[k] = vi;
    k++;
  }
  f.length = k;
  f.online = online;
  return f;
}
