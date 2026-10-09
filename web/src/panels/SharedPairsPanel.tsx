"use client";
import { type Replay } from "@/data/replay";
import { usePlayback } from "@/store/playback";
import { Button, Panel } from "@/ui";
import { formatClock } from "@/data/replay";
import { journeyMarks, journeyStage, journeyStart } from "@/data/sharedJourney";
import s from "./panels.module.css";

export function SharedPairsPanel({replay}:{replay:Replay}) {
  const t = usePlayback(x => x.t);
  const focusedPair = usePlayback(x => x.focusedPair);
  const shared=replay.manifest.shared;
  if(!shared)return null;
  const pair = shared.pairs.find(p => p.id === focusedPair);
  const openPair = (id: number, play = false) => {
    const p = shared.pairs.find(p => p.id === id); if (!p) return;
    const st = usePlayback.getState(); st.setPlaying(false); st.focusPair(id);
    st.select(replay.vehicleIndex.get(p.driver_id) ?? null); st.setFollow(false);
    if (st.hidden.shared) st.toggleState("shared");
    if (!st.showRequests.shared_only) st.toggleRequests("shared_only");
    st.seek(journeyStart(replay, p)); st.setSpeed(10); st.setPlaying(play);
  };
  return <Panel title={<h2 style={{fontSize:14,margin:0}}>Shared ride V1 · replay</h2>} aria-label="Cặp Shared V1">
    <p style={{fontSize:12,margin:"0 0 8px"}}>Cặp đã tạo: {shared.pairs.length} · Đi chung: {shared.pairs.filter(p=>p.actual_shared).length}. Cước 70%.</p>
    <label style={{display:"grid",gap:6,fontSize:12}}>Xem cặp và hai khách
      <select aria-label="Chọn cặp shared" value={focusedPair ?? ""} style={{width:"100%",minHeight:36}}
        onChange={e=>openPair(Number(e.target.value))}>
        <option value="" disabled>Chọn cặp…</option>{shared.pairs.map(p=><option key={p.id} value={p.id}>Cặp #{p.id} · Khách {p.rider_ids.join(" / ")} · Xe {p.driver_id}</option>)}</select>
    </label>
    {pair && <div className={s.journey}>
      <p className={s.journeyStage} data-testid="shared-journey-stage">{journeyStage(replay, pair, t)}</p>
      <Button size="sm" variant="primary" onClick={() => openPair(pair.id, true)}>Xem từ đầu · 10×</Button>
      <p className={s.legendHint}>Chọn mốc để tua. Điểm đón/trả của hai khách được ghi tên trên bản đồ.</p>
      <details className={s.journeyDetails}><summary>Các mốc đặt, ghép, đón và trả</summary>
      <ol className={s.journeyMarks}>{journeyMarks(replay, pair).map((mark, i) =>
        <li key={i}><button type="button" data-complete={t >= mark.t} onClick={() => {
          const st = usePlayback.getState(); st.setPlaying(false);
          st.select(replay.vehicleIndex.get(pair.driver_id) ?? null); st.seek(mark.t + 0.001);
          if (!st.showRequests.shared_only) st.toggleRequests("shared_only");
        }}><span>{formatClock(mark.t)}</span> {mark.label}</button></li>)}</ol>
      </details>
    </div>}
  </Panel>;
}
