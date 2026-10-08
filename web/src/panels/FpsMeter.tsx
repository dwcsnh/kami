"use client";
// `?debug=1`: frame statistics for AC03-6 (median and 5th percentile fps over a 60 s window of wall time).
// Results are also exposed as window.__kamiFps for automated reading.
import { useEffect, useRef, useState } from "react";
import { Button, Panel } from "@/ui";
import s from "./panels.module.css";

interface Stats { frames: number; median: number; p5: number; seconds: number; running: boolean }

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const i = Math.min(sorted.length - 1, Math.max(0, Math.round(q * (sorted.length - 1))));
  return sorted[i];
}

export function FpsMeter() {
  const [stats, setStats] = useState<Stats>({ frames: 0, median: 0, p5: 0, seconds: 0, running: false });
  const deltas = useRef<number[]>([]);
  const measuring = useRef<{ until: number } | null>(null);
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let shown = last;
    const loop = (now: number) => {
      const d = now - last;
      last = now;
      const arr = deltas.current;
      arr.push(d);
      const m = measuring.current;
      if (!m && arr.length > 600) arr.splice(0, arr.length - 600);
      if (now - shown > 500) {
        shown = now;
        const fps = arr.map((x) => 1000 / x).sort((a, b) => a - b);
        const st: Stats = { frames: arr.length, median: quantile(fps, 0.5), p5: quantile(fps, 0.05),
                            seconds: arr.reduce((a, x) => a + x, 0) / 1000, running: !!m };
        if (m && now >= m.until) {
          measuring.current = null;
          st.running = false;
        }
        setStats(st);
        (window as unknown as { __kamiFps?: Stats }).__kamiFps = st;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  const start = () => {
    deltas.current = [];
    measuring.current = { until: performance.now() + 60_000 };
  };
  (globalThis as unknown as { __kamiFpsStart?: () => void }).__kamiFpsStart = start;
  return (
    <Panel className={s.fps} aria-label="Thống kê khung hình">
      <span>fps trung vị <b>{stats.median.toFixed(1)}</b></span>
      <span>p5 <b>{stats.p5.toFixed(1)}</b></span>
      <span>{stats.frames} khung / {stats.seconds.toFixed(0)} s</span>
      <Button size="sm" onClick={start} disabled={stats.running}>{stats.running ? "Đang đo…" : "Đo 60 s"}</Button>
    </Panel>
  );
}
