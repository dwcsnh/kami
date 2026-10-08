// Playback state. The simulation clock `t` is the single time source: map layers and panels read it from here.
import { create } from "zustand";

export const SPEEDS = [1, 10, 60, 120, 300, 600] as const;
export type Mode = "vehicles" | "trajectories";

export interface PlaybackState {
  start: number;
  end: number;
  t: number;
  playing: boolean;
  speed: number;
  mode: Mode;
  hidden: Record<string, boolean>;   // state id → trail and vehicles hidden
  showOD: boolean;
  selected: number | null;           // vehicle index
  follow: boolean;
  panelOpen: boolean;
  chromeHidden: boolean;
  init(start: number, end: number): void;
  seek(t: number): void;
  step(dt: number): void;
  setPlaying(p: boolean): void;
  togglePlaying(): void;
  setSpeed(s: number): void;
  setMode(m: Mode): void;
  toggleState(id: string): void;
  setShowOD(v: boolean): void;
  select(vi: number | null): void;
  setFollow(v: boolean): void;
  setPanelOpen(v: boolean): void;
  toggleChrome(): void;
}

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

export const usePlayback = create<PlaybackState>((set, get) => ({
  start: 0,
  end: 1,
  t: 0,
  playing: false,
  speed: 60,
  mode: "vehicles",
  hidden: {},
  showOD: false,
  selected: null,
  follow: false,
  panelOpen: true,
  chromeHidden: false,
  init: (start, end) => set({ start, end, t: start, playing: false }),
  seek: (t) => set({ t: clamp(t, get().start, get().end) }),
  step: (dt) => {
    const { t, end, start } = get();
    const next = clamp(t + dt, start, end);
    set(next >= end ? { t: end, playing: false } : { t: next });
  },
  setPlaying: (p) => set((s) => ({ playing: p, t: p && s.t >= s.end ? s.start : s.t })),
  togglePlaying: () => get().setPlaying(!get().playing),
  setSpeed: (speed) => set({ speed }),
  setMode: (mode) => set({ mode }),
  toggleState: (id) => set((s) => ({ hidden: { ...s.hidden, [id]: !s.hidden[id] } })),
  setShowOD: (showOD) => set({ showOD }),
  select: (selected) => set({ selected, follow: selected === null ? false : get().follow }),
  setFollow: (follow) => set({ follow }),
  setPanelOpen: (panelOpen) => set({ panelOpen }),
  toggleChrome: () => set((s) => ({ chromeHidden: !s.chromeHidden })),
}));
