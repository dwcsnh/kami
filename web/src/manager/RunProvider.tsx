"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import { acceptFrame, emptyLive, type LiveState } from "./runState";
import { isTerminal, type Health, type RunDetail, type RunRow } from "./types";

interface State { online: boolean; ready: boolean; health: Health | null; runs: RunRow[]; active: RunDetail | null; live: LiveState; revision: number }
const initial: State = { online: false, ready: false, health: null, runs: [], active: null, live: emptyLive(), revision: 0 };
interface Context extends State { refresh: () => Promise<void>; details: (rows: RunRow[]) => Promise<RunDetail[]> }
const RunContext = createContext<Context>({ ...initial, refresh: async () => {}, details: async () => [] });
export function RunProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initial);
  const cache = useRef(new Map<number, RunDetail>());
  const refreshRef = useRef<() => Promise<void>>(async () => {});
  const details = useCallback(async (rows: RunRow[]) => {
    const result: RunDetail[] = [];
    let index = 0;
    await Promise.all(Array.from({ length: Math.min(4, rows.length) }, async () => {
      while (index < rows.length) {
        const row = rows[index++];
        let d = cache.current.get(row.id);
        if (!d || !isTerminal(d.status) || d.status !== row.status) {
          d = await api.detail(row.id);
          cache.current.set(row.id, d);
        }
        result.push(d);
      }
    }));
    return result.sort((a,b) => b.id-a.id);
  }, []);
  useEffect(() => {
    let disposed = false, busy = false;
    let source: EventSource | null = null, streamId: number | null = null;
    const abort = new AbortController();
    function close() { source?.close(); source = null; streamId = null; }
    function connect(id: number) {
      if (streamId === id) return;
      close(); streamId = id;
      setState(s => ({ ...s, live: emptyLive(id) }));
      const es = new EventSource("/api/v1/runs/" + id + "/stream");
      source = es;
      for (const kind of ["status", "progress", "metric", "resync", "terminal"]) es.addEventListener(kind, (ev) => {
        if (disposed || source !== es) return;
        try {
          const data: unknown = JSON.parse((ev as MessageEvent).data);
          setState(s => ({ ...s, live: acceptFrame(s.live, kind, data) }));
          if (kind === "resync") void poll();
          if (kind === "terminal") { close(); void poll(); }
        } catch { setState(s => ({ ...s, live: { ...s.live, gap: true } })); }
      });
      es.onerror = () => {
        if (!disposed && source === es) { setState(s => ({ ...s, live: { ...s.live, gap: true } })); void poll(); }
      };
    }
    async function poll() {
      if (disposed || busy) return;
      busy = true;
      // A separate deadline prevents a hung request from freezing the monitor forever.
      const deadline = AbortSignal.any([abort.signal, AbortSignal.timeout(10000)]);
      try {
        const [health, runs] = await Promise.all([api.health(deadline), api.runs(deadline)]);
        const running = runs.find(r => r.status === "running");
        const active = running ? await api.detail(running.id, deadline) : null;
        if (disposed) return;
        if (active) { cache.current.set(active.id, active); connect(active.id); } else close();
        setState(s => ({ ...s, health, runs, active, ready: true, online: true, revision: s.revision + 1 }));
      } catch {
        if (!disposed) setState(s => ({ ...s, ready: true, online: false }));
      } finally { busy = false; }
    }
    refreshRef.current = poll;
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => { disposed = true; clearInterval(timer); abort.abort(); close(); };
  }, []);
  const refresh = useCallback(() => refreshRef.current(), []);
  return <RunContext.Provider value={{ ...state, refresh, details }}>{children}</RunContext.Provider>;
}
export const useRuns = () => useContext(RunContext);
