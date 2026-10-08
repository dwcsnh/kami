// Vehicle counts per state at the displayed time (written by the map each frame, read by the legend).
// Only a change of the counts notifies subscribers.
import { create } from "zustand";

interface FrameStore {
  counts: number[];
  online: number;
  publish(counts: Uint32Array, online: number, t: number): void;
}

export const useFrameStore = create<FrameStore>((set, get) => ({
  counts: [],
  online: 0,
  publish: (counts, online) => {
    const cur = get().counts;
    let same = cur.length === counts.length && get().online === online;
    for (let i = 0; same && i < counts.length; i++) same = cur[i] === counts[i];
    if (!same) set({ counts: Array.from(counts), online });
  },
}));
