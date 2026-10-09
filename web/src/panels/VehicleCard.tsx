"use client";
// S03-11: details of the clicked vehicle at the displayed time; its route is highlighted on the map.
import { formatClock, type Replay } from "@/data/replay";
import { usePlayback } from "@/store/playback";
import { useThrottledT } from "@/store/useClock";
import { Badge, Button, IconButton, Panel } from "@/ui";
import { IconClose, IconCrosshair } from "@/ui/icons";
import s from "./panels.module.css";

const GROUP: Record<string, string> = { car: "Ô tô", bike: "Xe máy" };
const nf1 = new Intl.NumberFormat("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function VehicleCard({ replay, colors }: { replay: Replay; colors: string[] }) {
  const vi = usePlayback((x) => x.selected);
  const follow = usePlayback((x) => x.follow);
  const setFollow = usePlayback((x) => x.setFollow);
  const select = usePlayback((x) => x.select);
  const panelOpen = usePlayback((x) => x.panelOpen);
  const t = useThrottledT(200);
  if (vi === null) return null;
  const v = replay.vehicles[vi];
  const seg = replay.segmentAt(vi, t);
  const st = seg >= 0 ? replay.segState[seg] : -1;
  const riderId = seg >= 0 ? replay.segRider[seg] : -1;
  const trip = riderId >= 0 ? replay.rider(riderId) : undefined;
  const pair = replay.sharedPairAt(v.id,t);
  const onboard = pair ? replay.sharedOnboardAt(pair.id,t) : [];
  const km = replay.distanceAt(vi, t) / 1000;
  const clock = (x?: number) => (x === undefined ? "—" : formatClock(x));
  return (
    <Panel className={`${s.vehicleCard} ${panelOpen ? "" : s.vehicleCardWide}`} aria-label={`Xe ${v.id}`}
      title={<h2 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Xe #{v.id}</h2>}
      actions={<IconButton label="Đóng (Esc)" variant="bare" onClick={() => select(null)}><IconClose /></IconButton>}>
      <div style={{ marginBottom: 10 }}>
        {st >= 0 ? <Badge color={colors[st]}>{replay.states[st].label}</Badge> : <Badge>Ngoài ca</Badge>}
      </div>
      <dl className={s.dl}>
        <dt>Fleet</dt><dd>{v.fleet ?? "—"}</dd>
        <dt>Loại xe</dt><dd>{v.vehicle_type ?? "—"}</dd>
        <dt>Nhóm</dt><dd>{(v.group && GROUP[v.group]) ?? v.group ?? "—"}{v.seats ? ` · ${v.seats} chỗ` : ""}</dd>
        <dt>Ca làm việc</dt><dd>{formatClock(v.shift[0], false)}–{formatClock(v.shift[1], false)}</dd>
        <dt>Quãng đường đã chạy</dt><dd data-testid="vehicle-km">{nf1.format(km)} km</dd>
      </dl>
      <p className={s.sectionLabel}>Chuyến hiện tại</p>
      {pair&&<details open><summary>Cặp #{pair.id} · {onboard.length}/2 khách trên xe</summary>
        <p style={{fontSize:12}}>Khách {pair.rider_ids.map(id=>"#"+id).join(" và ")} · {onboard.length===2?"Đang đi chung":pair.overlap_end!==null&&t>=pair.overlap_end?"Đã kết thúc đi chung":"Chưa có hai khách trên xe"}</p>
        <ol style={{fontSize:12,paddingLeft:18}}>{pair.stops.map((stop,i)=>{
          const predicted=stop.kind==="pickup"?pair.predicted_pickup[stop.rider_id]:pair.predicted_dropoff[stop.rider_id];
          const actual=stop.kind==="pickup"?pair.pickups[stop.rider_id]:pair.dropoffs[stop.rider_id];
          return <li key={i}>{stop.kind==="pickup"?"Đón":"Trả"} #{stop.rider_id} · {actual!==undefined&&actual<=t?formatClock(actual):"dự kiến "+formatClock(predicted)}</li>;
        })}</ol>
        <p style={{fontSize:12}}>Đi chung thực tế: {nf1.format(Math.max(0,Math.min(t,pair.overlap_end??t)-(pair.overlap_start??t))/60)} phút · Dự kiến {nf1.format(pair.predicted_overlap_s/60)} phút</p>
        {pair.reason&&<p style={{fontSize:12}}>Lý do: {pair.reason}</p>}
      </details>}
      {trip ? (
        <dl className={s.dl}>
          <dt>Khách</dt><dd>#{trip.rider}</dd>
          <dt>Đặt xe</dt><dd>{clock(trip.request)}</dd>
          <dt>Nhận chuyến</dt><dd>{clock(trip.matched)}</dd>
          <dt>Đón dự kiến</dt><dd>{clock(trip.eta)}</dd>
          <dt>Đón thực tế</dt><dd>{trip.pickup !== undefined && trip.pickup <= t ? clock(trip.pickup) : "—"}</dd>
          <dt>Trả khách</dt><dd>{trip.dropoff !== undefined && trip.dropoff <= t ? clock(trip.dropoff) : "—"}</dd>
        </dl>
      ) : (
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>Không có chuyến tại thời điểm này.</p>
      )}
      <div className={s.cardActions}>
        <Button size="sm" variant={follow ? "primary" : "secondary"} onClick={() => setFollow(!follow)} aria-pressed={follow}>
          <IconCrosshair size={16} /> {follow ? "Đang đi theo xe" : "Đi theo xe"}
        </Button>
      </div>
    </Panel>
  );
}
