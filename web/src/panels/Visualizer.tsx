"use client";
// Fleet operation visualizer (sprint 03): map + KPI/charts + playback + legend, from a kami.replay folder.
import { useEffect, useMemo, useState } from "react";
import { StaticReplaySource, loadReplay } from "@/data/loader";
import { Replay } from "@/data/replay";
import { ReplayDisplay } from "@/data/display";
import { MapView } from "@/map/MapView";
import { paletteFromUrl, stateHex, stateRgb } from "@/map/palette";
import { usePlayback } from "@/store/playback";
import { useClock } from "@/store/useClock";
import { Button } from "@/ui";
import { FpsMeter } from "./FpsMeter";
import { HeaderPanel } from "./HeaderPanel";
import { LegendPanel } from "./LegendPanel";
import { MapControls } from "./MapControls";
import { MetricsPanel } from "./MetricsPanel";
import { LoadError, Loading, TokenMissing } from "./Messages";
import { PlaybackBar } from "./PlaybackBar";
import { VehicleCard } from "./VehicleCard";
import { SharedPairsPanel } from "./SharedPairsPanel";
import s from "./panels.module.css";

export const DEFAULT_REPLAY = "/fixtures/shared_v1_walkthrough";
const TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

export default function Visualizer() {
  const [replay, setReplay] = useState<Replay | null>(null);
  const [status, setStatus] = useState("Đang tải dữ liệu phát lại…");
  const [error, setError] = useState<string | null>(null);
  const params = useMemo(() => new URLSearchParams(typeof window === "undefined" ? "" : window.location.search), []);
  const url = params.get("replay") ?? DEFAULT_REPLAY;
  const debug = params.get("debug") === "1";
  const palette = useMemo(paletteFromUrl, []);
  const chromeHidden = usePlayback((x) => x.chromeHidden);
  const toggleChrome = usePlayback((x) => x.toggleChrome);
  useClock();

  useEffect(() => {
    let cancelled = false;
    loadReplay(new StaticReplaySource(url), setStatus)
      .then((docs) => {
        if (cancelled) return;
        setStatus("Đang dựng dữ liệu…");
        const rp = new Replay(docs);
        const st = usePlayback.getState();
        st.init(rp.start, rp.end);
        st.focusPair(rp.manifest.shared?.pairs[0]?.id ?? null);
        const t = Number(params.get("t"));
        if (params.get("t") && Number.isFinite(t)) st.seek(t);
        if (params.get("mode") === "trajectories") st.setMode("trajectories");
        if (params.get("panel") === "0") st.setPanelOpen(false);
        const sel = params.get("select");
        if (sel !== null && rp.vehicleIndex.has(Number(sel))) st.select(rp.vehicleIndex.get(Number(sel))!);
        if (params.get("od") === "1") st.setShowOD(true);
        for (const id of (params.get("hide") ?? "").split(",").filter(Boolean)) st.toggleState(id);
        (window as unknown as { __kami?: unknown }).__kami = { replay: rp, store: usePlayback };
        setReplay(rp);
      })
      .catch((e: unknown) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [url, params]);

  const display = useMemo(() => replay ? new ReplayDisplay(replay) : null, [replay]);
  const colorsRgb = useMemo(() => (display ? stateRgb(display.states, palette) : []), [display, palette]);
  const colorsHex = useMemo(() => (display ? stateHex(display.states, palette) : []), [display, palette]);

  if (error) return <div className={s.root}><LoadError error={error} url={url} /></div>;
  if (!replay) return <div className={s.root}><Loading message={status} /></div>;
  return (
    <main className={`${s.root} ${chromeHidden ? s.chromeHidden : ""}`} data-palette={palette}>
      {TOKEN ? <MapView replay={replay} display={display!} token={TOKEN} colors={colorsRgb} /> : <TokenMissing />}
      <div className={s.leftColumn}>
        <HeaderPanel replay={replay} />
        <SharedPairsPanel replay={replay}/>
        <LegendPanel replay={replay} display={display!} colors={colorsHex} />
        {TOKEN && <MapControls />}
      </div>
      <MetricsPanel replay={replay} colors={colorsHex} />
      <VehicleCard replay={replay} colors={colorsHex} />
      <PlaybackBar replay={replay} />
      {chromeHidden && (
        <div className={s.showChrome}><Button size="sm" onClick={toggleChrome}>Hiện bảng điều khiển (F)</Button></div>
      )}
      {debug && <FpsMeter />}
    </main>
  );
}
