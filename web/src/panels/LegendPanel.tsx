"use client";
// Legend = state toggles (S03-8): colour, label and number of vehicles in the state at the displayed time.
import type { Replay } from "@/data/replay";
import type { ReplayDisplay } from "@/data/display";
import { tokens } from "@/design/tokens";
import { useFrameStore } from "@/map/frameStore";
import { usePlayback } from "@/store/playback";
import { LegendChip, Panel } from "@/ui";
import s from "./panels.module.css";

export function LegendPanel({ replay, display, colors }: { replay: Replay; display: ReplayDisplay; colors: string[] }) {
  const hidden = usePlayback((x) => x.hidden);
  const toggle = usePlayback((x) => x.toggleState);
  const counts = useFrameStore((x) => x.counts);
  const online = useFrameStore((x) => x.online);
  const t = usePlayback(x => x.t);
  const showRequests = usePlayback(x => x.showRequests);
  const toggleRequests = usePlayback(x => x.toggleRequests);
  const waiting = display.waitingAt(t);
  return (
    <Panel className={s.legend} title="Trạng thái xe" aria-label="Chú giải trạng thái xe">
      {display.states.map((st, i) => (
        <LegendChip key={st.id} color={colors[i]} label={st.label} count={counts[i] ?? 0} on={!hidden[st.id]}
          emphasis={st.id === "on_trip" || st.id === "shared"} onToggle={() => toggle(st.id)} />
      ))}
      {!replay.manifest.shared && <LegendChip color={tokens.color.primary} label="Xe share" count={0}
        on={!hidden.shared} onToggle={() => toggle("shared")} emphasis />}
      <div className={s.legendFoot}>
        <span>Đang hoạt động</span>
        <span>{online} / {replay.vehicles.length} xe</span>
      </div>
      {replay.manifest.shared && <p className={s.legendHint}>Xe share đang phục vụ cặp ghép, gồm cả chặng đi đón.</p>}
      {!replay.manifest.shared && <p className={s.legendHint}>Replay này chưa có cặp Shared. <a href="/visualizer?replay=/fixtures/shared_v1_walkthrough">Xem Shared từ đầu đến cuối</a>.</p>}
      <h3 className={s.sectionLabel}>Người đặt đang chờ</h3>
      <LegendChip color={tokens.color.primary} label="Đặt Shared (S)"
        count={waiting.filter(r => r.preference === "shared_only").length} on={showRequests.shared_only}
        onToggle={() => toggleRequests("shared_only")} />
      <LegendChip color={tokens.color.state.A.pickup} label="Đặt Exclusive (E)"
        count={waiting.filter(r => r.preference === "exclusive_only").length} on={showRequests.exclusive_only}
        onToggle={() => toggleRequests("exclusive_only")} />
      <p className={s.legendHint}>Điểm đón hiện từ lúc đặt đến khi được đón hoặc hủy. Rê chuột để xem mã khách.</p>
    </Panel>
  );
}
