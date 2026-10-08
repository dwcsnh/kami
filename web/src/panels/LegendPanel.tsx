"use client";
// Legend = state toggles (S03-8): colour, label and number of vehicles in the state at the displayed time.
import type { Replay } from "@/data/replay";
import { useFrameStore } from "@/map/frameStore";
import { usePlayback } from "@/store/playback";
import { LegendChip, Panel } from "@/ui";
import s from "./panels.module.css";

export function LegendPanel({ replay, colors }: { replay: Replay; colors: string[] }) {
  const hidden = usePlayback((x) => x.hidden);
  const toggle = usePlayback((x) => x.toggleState);
  const counts = useFrameStore((x) => x.counts);
  const online = useFrameStore((x) => x.online);
  return (
    <Panel className={s.legend} title="Trạng thái xe" aria-label="Chú giải trạng thái xe">
      {replay.states.map((st, i) => (
        <LegendChip key={st.id} color={colors[i]} label={st.label} count={counts[i] ?? 0} on={!hidden[st.id]}
          emphasis={st.id === "on_trip"} onToggle={() => toggle(st.id)} />
      ))}
      <div className={s.legendFoot}>
        <span>Đang hoạt động</span>
        <span>{online} / {replay.vehicles.length} xe</span>
      </div>
    </Panel>
  );
}
