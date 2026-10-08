"use client";
// Advances the simulation clock while playing (wall time × speed), and keyboard shortcuts:
// Space play/pause · ←/→ ∓1 simulated minute · F map full screen (hide panels) · Esc deselect vehicle.
import { useEffect, useState } from "react";
import { usePlayback } from "./playback";

export function useClock(): void {
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(now - last, 250) / 1000;   // a background tab must not jump ahead
      last = now;
      const s = usePlayback.getState();
      if (s.playing) s.step(dt * s.speed);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const s = usePlayback.getState();
      if (e.key === " " && !(el && el.tagName === "BUTTON")) {
        e.preventDefault();
        s.togglePlaying();
      } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        if (el && el.getAttribute("role") === "slider") return;
        e.preventDefault();
        e.stopPropagation();                         // keep the map from panning
        s.seek(s.t + (e.key === "ArrowRight" ? 60 : -60));
      } else if (e.key === "f" || e.key === "F") {
        s.toggleChrome();
      } else if (e.key === "Escape") {
        s.select(null);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);
}

/** The clock, refreshed at most every `ms` milliseconds of wall time (panels do not need 60 Hz). */
export function useThrottledT(ms = 200): number {
  const [t, setT] = useState(() => usePlayback.getState().t);
  useEffect(() => {
    let last = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const unsub = usePlayback.subscribe((s, prev) => {
      if (s.t === prev.t) return;
      const now = performance.now();
      if (now - last >= ms) {
        last = now;
        setT(s.t);
      } else if (!timer) {
        timer = setTimeout(() => {
          timer = null;
          last = performance.now();
          setT(usePlayback.getState().t);
        }, ms - (now - last));
      }
    });
    return () => {
      unsub();
      if (timer) clearTimeout(timer);
    };
  }, [ms]);
  return t;
}
