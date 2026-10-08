"use client";
import type { Replay } from "@/data/replay";
import { formatClock } from "@/data/replay";
import { Badge, Panel, Segmented, Toggle } from "@/ui";
import { usePlayback } from "@/store/playback";
import s from "./panels.module.css";

export function HeaderPanel({ replay }: { replay: Replay }) {
  const mode = usePlayback((x) => x.mode);
  const setMode = usePlayback((x) => x.setMode);
  const showOD = usePlayback((x) => x.showOD);
  const setShowOD = usePlayback((x) => x.setShowOD);
  const m = replay.manifest;
  const t0 = m.time.scenario_start ?? m.time.start;
  return (
    <Panel className={s.header} aria-label="Kịch bản">
      <div className={s.brandRow}>
        <span className={s.logo}><span className={s.logoMark} aria-hidden="true" />kami</span>
        <span className={s.pageTitle}>· Bản đồ vận hành</span>
      </div>
      <p className={s.areaName}>{m.area?.name ?? m.run.scenario ?? "Kịch bản"}</p>
      <div className={s.meta}>
        <Badge>{formatClock(t0, false)}–{formatClock(m.time.end, false)}</Badge>
        <Badge>{m.counts.vehicles} xe</Badge>
        {m.run.policy && <Badge>policy {m.run.policy}</Badge>}
        {m.run.seed !== undefined && <Badge>seed {m.run.seed}</Badge>}
      </div>
      <div className={s.stack}>
        <Segmented label="Chế độ bản đồ" value={mode} onChange={setMode}
          options={[{ value: "vehicles", label: "Xe di chuyển" }, { value: "trajectories", label: "Quỹ đạo" }]} />
        <Toggle checked={showOD} onChange={setShowOD} label="Cung OD nhu cầu (±7,5 phút)" />
      </div>
    </Panel>
  );
}
