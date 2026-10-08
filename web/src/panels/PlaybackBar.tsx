"use client";
// S03-9: play/pause, timeline with hour ticks, ±1 minute, speed, simulation clock.
import { useMemo } from "react";
import { formatClock, type Replay } from "@/data/replay";
import { SPEEDS, usePlayback } from "@/store/playback";
import { useThrottledT } from "@/store/useClock";
import { IconBack, IconForward, IconPause, IconPlay } from "@/ui/icons";
import { IconButton, Panel, Segmented, Timeline } from "@/ui";
import s from "./panels.module.css";

export function PlaybackBar({ replay }: { replay: Replay }) {
  const t = useThrottledT(100);
  const playing = usePlayback((x) => x.playing);
  const toggle = usePlayback((x) => x.togglePlaying);
  const seek = usePlayback((x) => x.seek);
  const speed = usePlayback((x) => x.speed);
  const setSpeed = usePlayback((x) => x.setSpeed);
  const { start, end } = replay;
  const ticks = useMemo(() => {
    const out: { value: number; label: string }[] = [];
    const step = end - start > 3 * 3600 ? 3600 : 1800;
    for (let v = Math.ceil(start / step) * step; v <= end; v += step) out.push({ value: v, label: formatClock(v, false) });
    return out;
  }, [start, end]);
  const t0 = replay.manifest.time.scenario_start ?? start;
  return (
    <Panel className={s.playback} bodyClassName={s.playbackBody} aria-label="Điều khiển phát lại">
      <div className={s.transport}>
        <IconButton label="Lùi 1 phút (←)" variant="bare" onClick={() => seek(usePlayback.getState().t - 60)}>
          <IconBack />
        </IconButton>
        <IconButton label={playing ? "Tạm dừng (Space)" : "Phát (Space)"} variant="primary" round onClick={toggle}>
          {playing ? <IconPause size={20} /> : <IconPlay size={20} />}
        </IconButton>
        <IconButton label="Tới 1 phút (→)" variant="bare" onClick={() => seek(usePlayback.getState().t + 60)}>
          <IconForward />
        </IconButton>
      </div>
      <div className={s.clock} aria-live="off">
        <span className={s.clockTime} data-testid="clock">{formatClock(t)}</span>
        <span className={s.clockSub}>Khung {formatClock(t0, false)}–{formatClock(end, false)}</span>
      </div>
      <Timeline label="Thời điểm mô phỏng" value={t} min={start} max={end} onChange={seek} ticks={ticks}
        format={(v) => formatClock(v)} />
      <Segmented label="Tốc độ phát" size="sm" value={speed} onChange={setSpeed}
        options={SPEEDS.map((v) => ({ value: v, label: `${v}×`, title: `${v} giây mô phỏng mỗi giây` }))} />
    </Panel>
  );
}
