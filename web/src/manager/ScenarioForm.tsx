"use client";
import { useState } from "react";
import { Button, Toggle } from "@/ui";
import { Field } from "./components";
import { changeSource, PRESETS, scenarioPayload, secondsToTime, selectFleet, sourceParameters, timeToSeconds, withSourceParameters } from "./scenarioDraft";
import type { Entity, Fleet, RunSpec } from "./types";
import s from "./manager.module.css";
import { Dropdown } from "./Dropdown";
export default function ScenarioForm({ base, fleets, busy, error, onSave, onCancel }: { base:RunSpec; fleets:Entity<Fleet>[]; busy:boolean; error:unknown; onSave:(v:RunSpec)=>void; onCancel:()=>void }) {
  const [spec,setSpec]=useState(()=>structuredClone(base));
  const source=spec.scenario.source,p=sourceParameters(source);
  const preset=PRESETS[source.preset as keyof typeof PRESETS]??PRESETS.weekday_am_peak;
  const [start,setStart]=useState(secondsToTime(typeof p.t_start==="number"?p.t_start:preset.start));
  const [end,setEnd]=useState(secondsToTime(typeof p.t_end==="number"?p.t_end:preset.end));
  const [localError,setLocalError]=useState("");
  const scenario=(patch:Record<string,unknown>)=>setSpec(v=>({...v,scenario:{...v.scenario,...patch}}));
  const updateSource=(patch:Record<string,unknown>)=>scenario({source:{...source,...patch}});
  const params=(patch:Record<string,unknown>)=>scenario({source:withSourceParameters(source,patch)});
  const network=spec.scenario.network??{kind:"grid"},zones=spec.scenario.zones??{kind:"square"};
  const supported=["preset","synthetic","zonal"].includes(source.kind);
  const numeric=(v:string)=>v===""?null:Number(v);
  const weather=(p.weather??[]) as [number,string][];
  const incidents=(p.incidents??[]) as Record<string,unknown>[];
  function setKind(kind:string) {
    if(source.kind!==kind&&!window.confirm("Đổi nguồn demand sẽ thay các tham số của nguồn hiện tại. Tiếp tục?"))return;
    scenario({source:changeSource(source,kind)});
  }
  function changePreset(key:string) {
    updateSource({preset:key});
    const next=PRESETS[key as keyof typeof PRESETS];
    if(next){setStart(secondsToTime(next.start));setEnd(secondsToTime(next.end));}
  }
  function updateIncident(index:number,patch:Record<string,unknown>) { params({incidents:incidents.map((v,i)=>i===index?{...v,...patch}:v)}); }
  const inline=(spec.fleets??[]).filter(x=>!("ref" in x));
  const unknownRefs=(spec.fleets??[]).filter(x=>"ref" in x&&!fleets.some(f=>x.ref===f.id||x.ref===f.name));
  return <form className={s.card+" "+s.form} onSubmit={e=>{
    e.preventDefault();setLocalError("");
    try {
      let next=spec;
      if(supported){const a=timeToSeconds(start),b=timeToSeconds(end);if(b<=a)throw new Error("Giờ kết thúc phải sau giờ bắt đầu.");next={...spec,scenario:{...spec.scenario,source:withSourceParameters(source,{t_start:a,t_end:b})}};}
      if(!next.scenario.name.trim())throw new Error("Tên kịch bản không được để trống.");
      if(!next.fleets?.length)throw new Error("Chọn ít nhất một fleet cho kịch bản.");
      onSave(scenarioPayload(next));
    }catch(e){setLocalError(e instanceof Error?e.message:String(e));}
  }}>
    <h2>{base.scenario.name?"Chỉnh sửa kịch bản":"Kịch bản mới"}</h2>
    <nav className={s.formNav} aria-label="Các phần cấu hình">{[["identity","Thông tin chung"],["network","Bản đồ"],["demand","Nhu cầu"],["fleet","Đội xe"],["collection","Kết quả"]].map(([id,label],i)=><a key={id} href={"#scenario-"+id}><span>{i+1}</span>{label}</a>)}</nav>
    {localError&&<p role="alert" className={s.error}>{localError}</p>}
    <div id="scenario-identity" className={s.formGrid}>
      <Field label="Tên kịch bản" error={error} path="scenario.name"><input required value={spec.scenario.name} onChange={e=>scenario({name:e.target.value})}/></Field>
      <Field label="Nhãn lần chạy" hint="Để trống để dùng tên kịch bản."><input value={spec.name} onChange={e=>setSpec(v=>({...v,name:e.target.value}))}/></Field>
      <Field label="Seed" error={error} path="seed" hint="Để trống để dùng seed của scenario."><input type="number" step="1" value={spec.seed??""} onChange={e=>setSpec(v=>({...v,seed:numeric(e.target.value)}))}/></Field>
      <Field label="CRN seed" error={error} path="crn_seed" hint="Để trống để dùng seed hiệu lực của run."><input type="number" step="1" value={spec.crn_seed??""} onChange={e=>setSpec(v=>({...v,crn_seed:numeric(e.target.value)}))}/></Field>
    </div>
    <fieldset id="scenario-network"><legend>01 · Bản đồ & vùng hoạt động</legend><div className={s.formGrid}>
      <Field label="Mạng đường"><Dropdown value={String(network.kind)} onValueChange={value=>{
        if(network.kind!==value&&!window.confirm("Đổi mạng đường sẽ thay cấu hình mạng hiện tại. Tiếp tục?"))return;
        scenario({network:value==="grid"?{kind:"grid",width_m:8000,height_m:8000,spacing_m:250,speed_kmh:25}:{kind:"road",name:"hanoi",backend:"auto"}});
      }}><option value="grid">Lưới synthetic</option><option value="road">Mạng đường thật</option></Dropdown></Field>
      <Field label="Hệ zone"><Dropdown value={String(zones.kind)} onValueChange={value=>{
        if(zones.kind!==value&&!window.confirm("Đổi hệ zone sẽ thay tham số zone hiện tại. Tiếp tục?"))return;
        scenario({zones:value==="square"?{kind:"square",cell_m:1000}:value==="h3"?{kind:"h3",resolution:8}:{kind:"file",name:"hanoi_h3_r8"}});
      }}><option value="square">Ô vuông</option><option value="h3">H3</option><option value="file">Zone từ dữ liệu mạng</option></Dropdown></Field>
      {network.kind==="road"?<>
        <Field label="Tên mạng đường" error={error} path="scenario.network.name"><input required value={String(network.name??"")} onChange={e=>scenario({network:{...network,name:e.target.value}})}/></Field>
        <Field label="Thư mục dữ liệu mạng" hint="Đường dẫn trên máy chạy backend; để trống dùng mặc định."><input value={String(network.data_root??"")} onChange={e=>scenario({network:{...network,data_root:e.target.value||null}})}/></Field>
      </>:["width_m","height_m","spacing_m","speed_kmh"].map((key,i)=><Field key={key} label={["Chiều rộng lưới (m)","Chiều cao lưới (m)","Khoảng cách node (m)","Tốc độ (km/h)"][i]} error={error} path={"scenario.network."+key}><input type="number" min="0.1" step="any" required value={String(network[key]??"")} onChange={e=>scenario({network:{...network,[key]:numeric(e.target.value)}})}/></Field>)}
      <Field label={zones.kind==="square"?"Kích thước zone (m)":zones.kind==="h3"?"Độ phân giải H3":"Tên bộ zone"} error={error} path={"scenario.zones."+(zones.kind==="square"?"cell_m":zones.kind==="h3"?"resolution":"name")}>
        <input required type={zones.kind==="file"?"text":"number"} min={zones.kind==="h3"?0:0.1} max={zones.kind==="h3"?15:undefined} step={zones.kind==="h3"?1:"any"} value={String(zones.kind==="square"?zones.cell_m??1000:zones.kind==="h3"?zones.resolution??8:zones.name??"")} onChange={e=>scenario({zones:{...zones,[zones.kind==="square"?"cell_m":zones.kind==="h3"?"resolution":"name"]:zones.kind==="file"?e.target.value:numeric(e.target.value)}})}/>
      </Field>
    </div>{network.kind==="road"&&<p className={s.muted}>Mạng đường và zone phải có sẵn trên máy chạy backend. Thiếu dữ liệu sẽ được báo trong kết quả run.</p>}</fieldset>
    <fieldset id="scenario-demand"><legend>02 · Nhu cầu di chuyển & thời gian</legend><div className={s.formGrid}>
      <Field label="Nguồn demand"><Dropdown value={source.kind} onValueChange={value=>setKind(value)}><option value="synthetic">Synthetic theo tham số</option><option value="preset">Preset có sẵn</option><option value="zonal">Demand theo zone</option>{!supported&&<option value={source.kind}>{source.kind} (giữ cấu hình hiện có)</option>}</Dropdown></Field>
      {source.kind==="preset"&&<Field label="Preset"><Dropdown value={source.preset??"weekday_am_peak"} onValueChange={value=>changePreset(value)}>{Object.entries(PRESETS).map(([key,v])=><option key={key} value={key}>{v.label}</option>)}</Dropdown></Field>}
      {supported?<>
        <Field label="Giờ bắt đầu" error={error} path="scenario.source.t_start"><input type="text" pattern="[0-9]{1,3}:[0-5][0-9](:[0-5][0-9])?" required value={start} onChange={e=>setStart(e.target.value)}/></Field>
        <Field label="Giờ kết thúc" error={error} path="scenario.source.t_end"><input type="text" pattern="[0-9]{1,3}:[0-5][0-9](:[0-5][0-9])?" required value={end} onChange={e=>setEnd(e.target.value)}/></Field>
        <Field label="Demand cơ sở (request/giờ)" error={error} path="scenario.source.demand_per_hour"><input type="number" min="0" step="any" required value={source.demand_per_hour??200} onChange={e=>updateSource({demand_per_hour:numeric(e.target.value)})}/></Field>
        {source.kind!=="preset"&&<Field label="Profile demand"><Dropdown value={Array.isArray(p.profile)?"custom":String(p.profile??"weekday")} onValueChange={value=>params({profile:value})}><option value="weekday">Ngày thường</option><option value="weekend">Cuối tuần</option>{Array.isArray(p.profile)&&<option value="custom">Profile 24 giờ hiện có</option>}</Dropdown></Field>}
      </>:<p className={s.notice}>Nguồn {source.kind} được giữ nguyên khi lưu. Bộ chỉnh sửa chi tiết nguồn này chưa có; các cấu hình khác vẫn chỉnh được.</p>}
    </div></fieldset>
    <fieldset id="scenario-fleet"><legend>03 · Đội xe tham gia</legend><p className={s.muted}>Chọn một hoặc nhiều đội xe; số lượng phương tiện lấy từ cấu hình đã lưu.</p>
      {!fleets.length&&<p className={s.warning}>Chưa có fleet. Tạo fleet ở trang Fleet & loại xe trước khi chạy.</p>}
      <div className={s.checkList}>{fleets.map(f=><label className={s.check} key={f.id}><input type="checkbox" checked={(spec.fleets??[]).some(x=>"ref" in x&&(x.ref===f.id||x.ref===f.name))} onChange={e=>setSpec(v=>selectFleet(v,f,e.target.checked))}/>{f.name} · {f.spec.composition.reduce((n,c)=>n+c.count,0)} xe</label>)}</div>
      {inline.length>0&&<p className={s.notice}>Fleet kèm trực tiếp trong mẫu được giữ nguyên: {inline.map(f=>String("name" in f?f.name:"fleet")).join(", ")}.</p>}
      {unknownRefs.length>0&&<p className={s.warning}>Mẫu có tham chiếu fleet không còn trong danh sách. Khi lưu, backend sẽ kiểm tra các tham chiếu này.</p>}
    </fieldset>
    {supported&&<details><summary>Thời tiết & sự cố</summary><fieldset><legend>Lịch thời tiết</legend>
      {source.kind==="preset"&&<p className={s.muted}>Không thêm dòng sẽ giữ lịch thời tiết của preset. Các dòng mới thay lịch hiện tại.</p>}
      {weather.map((w,i)=><div className={s.row} key={i}><Field label={"Thời tiết lúc "+(i+1)}><input type="time" step="1" value={secondsToTime(w[0])} required onChange={e=>{if(e.target.value)params({weather:weather.map((x,j)=>j===i?[timeToSeconds(e.target.value),x[1]]:x)});}}/></Field>
        <Field label={"Trạng thái thời tiết "+(i+1)}><Dropdown value={w[1]} onValueChange={value=>params({weather:weather.map((x,j)=>j===i?[x[0],value]:x)})}>{["clear","rain","heavy_rain"].map(v=><option key={v} value={v}>{v==="clear"?"Trời quang":v==="rain"?"Mưa":"Mưa lớn"}</option>)}{!["clear","rain","heavy_rain"].includes(w[1])&&<option>{w[1]}</option>}</Dropdown></Field>
        <Button onClick={()=>params({weather:weather.filter((_,j)=>j!==i)})}>Bỏ thời tiết {i+1}</Button></div>)}
      <Button onClick={()=>params({weather:[...weather,[timeToSeconds(start),"rain"]]})}>+ Thêm thời tiết</Button>
    </fieldset><fieldset><legend>Sự cố giao thông</legend>
      {source.kind==="preset"&&<p className={s.muted}>Preset có thể đã chứa sự cố. Không thêm dòng sẽ giữ lịch của preset.</p>}
      {incidents.map((inc,i)=><div className={s.card} key={i}><div className={s.formGrid}>
        {["t_offset","duration","radius_m","factor"].map((key,j)=><Field key={key} label={["Sau giờ bắt đầu (giây)","Thời lượng sự cố (giây)","Bán kính ảnh hưởng (m)","Hệ số chậm"][j]}><input type="number" min="0" step="any" required value={String(inc[key]??[0,600,500,2][j])} onChange={e=>updateIncident(i,{[key]:numeric(e.target.value)})}/></Field>)}
        <Field label="Vị trí sự cố"><Dropdown value={typeof inc.at==="number"?"node":typeof inc.at==="object"?"lonlat":"hotspot"} onValueChange={value=>updateIncident(i,{at:value==="node"?0:value==="lonlat"?{lon:105.85,lat:21.03}:"hotspot0"})}><option value="hotspot">Hotspot</option><option value="node">ID node</option><option value="lonlat">Kinh độ / vĩ độ</option></Dropdown></Field>
        {typeof inc.at==="object"&&inc.at!==null?["lon","lat"].map(k=><Field key={k} label={k==="lon"?"Kinh độ sự cố":"Vĩ độ sự cố"}><input type="number" step="any" required min={k==="lon"?-180:-90} max={k==="lon"?180:90} value={String((inc.at as Record<string,unknown>)[k]??"")} onChange={e=>updateIncident(i,{at:{...(inc.at as object),[k]:numeric(e.target.value)}})}/></Field>):<Field label={typeof inc.at==="number"?"Node sự cố":"Hotspot sự cố"}><input required type={typeof inc.at==="number"?"number":"text"} min="0" value={String(inc.at??"hotspot0")} onChange={e=>updateIncident(i,{at:typeof inc.at==="number"?numeric(e.target.value):e.target.value})}/></Field>}
      </div><Button onClick={()=>params({incidents:incidents.filter((_,j)=>j!==i)})}>Bỏ sự cố {i+1}</Button></div>)}
      <Button onClick={()=>params({incidents:[...incidents,{t_offset:0,duration:600,at:"hotspot0",radius_m:500,factor:2}]})}>+ Thêm sự cố</Button>
    </fieldset></details>}
    <fieldset id="scenario-collection"><legend>04 · Thu thập kết quả</legend><Toggle label="Thu thập chuỗi thời gian" checked={spec.sim_config?.timeseries_interval_s!==null} onChange={checked=>setSpec(v=>({...v,sim_config:{...v.sim_config,timeseries_interval_s:checked?60:null}}))}/><div className={s.formGrid}>
      <Field label="Khoảng lấy metric (giây)" error={error} path="sim_config.timeseries_interval_s"><input type="number" min="0.1" step="any" disabled={spec.sim_config?.timeseries_interval_s===null} required value={spec.sim_config?.timeseries_interval_s===null?"":String(spec.sim_config?.timeseries_interval_s??60)} onChange={e=>setSpec(v=>({...v,sim_config:{...v.sim_config,timeseries_interval_s:numeric(e.target.value)}}))}/></Field>
      <Field label="Thời gian hoàn tất chuyến sau demand (giây)" hint="Để trống dùng mặc định engine (3.600 giây)."><input type="number" min="0" step="any" value={String(spec.sim_config?.drain_s??"")} onChange={e=>setSpec(v=>{const config={...v.sim_config};if(e.target.value==="")delete config.drain_s;else config.drain_s=Number(e.target.value);return {...v,sim_config:config};})}/></Field>
    </div></fieldset>
    <p className={s.muted}>Matching, pricing nâng cao và mô hình EV sẽ được bổ sung khi backend hỗ trợ.</p>
    <div className={s.formFooter}><p>Lưu cấu hình để bắt đầu một lần chạy mới.</p><div className={s.actions}><Button disabled={busy} onClick={onCancel}>Đóng form</Button><Button type="submit" variant="primary" disabled={busy}>{busy?"Đang lưu…":"Lưu kịch bản"}</Button></div></div>
  </form>;
}
