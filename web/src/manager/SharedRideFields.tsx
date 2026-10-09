"use client";
import { Toggle } from "@/ui";
import { Field } from "./components";
import { sharedDraft, minutesToSeconds, secondsToMinutes, type SharedConfig } from "./sharedDraft";
import s from "./manager.module.css";

export function SharedRideFields({ value, error, onChange }: { value: unknown; error: unknown; onChange: (v: SharedConfig) => void }) {
  const cfg=sharedDraft(value), enabled=Boolean(value && cfg.enabled);
  const patch=(v:Partial<SharedConfig>)=>onChange({...cfg,...v});
  return <fieldset id="scenario-shared"><legend>04 · Shared ride V1</legend>
    <Toggle label="Bật Shared ride V1" checked={enabled} onChange={checked=>patch({enabled:checked})}/>
    <p className={s.muted}>Shared Only chờ ghép hai khách; Exclusive Only đi riêng. Mỗi khách Shared trả 70% cước đi riêng đã báo, kể cả khi mất đối tác sau đón.</p>
    {enabled&&<><div className={s.formGrid}>
      {(["shared_only","exclusive_only"] as const).map(key=><Field key={key} label={key==="shared_only"?"Tỷ lệ Shared Only":"Tỷ lệ Exclusive Only"} error={error} path={"sim_config.shared_ride.preference_weights."+key} hint="Trọng số tương đối; backend chuẩn hóa tổng thành 100%.">
        <input required type="number" min="0" step="any" value={cfg.preference_weights[key]} onChange={e=>patch({preference_weights:{...cfg.preference_weights,[key]:Number(e.target.value)}})}/>
      </Field>)}
      {(["max_pickup_wait_s","max_shared_extra_ride_s"] as const).map(key=><Field key={key} label={key==="max_pickup_wait_s"?"Hạn đón tổng (phút)":"Phần tăng trên xe tối đa (phút)"} error={error} path={"sim_config.shared_ride."+key} hint={key==="max_pickup_wait_s"?"Tính từ lúc đặt; áp dụng cả Shared và Exclusive trong kịch bản V1.":"Kiểm tra độc lập cho từng khách, gồm thời gian đón/trả người kia."}>
        <input required type="number" min={key==="max_pickup_wait_s"?.001:0} step="any" value={secondsToMinutes(cfg[key])} onChange={e=>patch({[key]:minutesToSeconds(Number(e.target.value))})}/>
      </Field>)}
      <Field label="Bán kính ứng viên (m)" error={error} path="sim_config.shared_ride.candidate_radius_m" hint="V1 yêu cầu cả hai điểm đón và hai điểm đến gần nhau."><input required type="number" min="0.1" step="any" value={cfg.candidate_radius_m} onChange={e=>patch({candidate_radius_m:Number(e.target.value)})}/></Field>
    </div><p className={s.notice}>Kiểm tra chỗ ngồi, nhóm xe và đường đi thực. Pin, sạc và tương thích sản phẩm EV chưa được mô phỏng.</p></>}
  </fieldset>;
}
