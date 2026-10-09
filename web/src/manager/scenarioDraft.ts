import type { Entity, Fleet, Ref, RunSpec, Source } from "./types";
export const PRESETS = {
  weekday_am_peak: { label:"Cao điểm sáng", start:25200, end:36000 },
  weekday_pm_peak: { label:"Cao điểm chiều", start:59400, end:70200 },
  weekday_offpeak: { label:"Ngoài giờ cao điểm", start:46800, end:57600 },
  weekend: { label:"Cuối tuần", start:36000, end:50400 },
  rain: { label:"Trời mưa", start:59400, end:70200 },
  accident: { label:"Sự cố giao thông", start:25200, end:36000 },
  undersupply: { label:"Thiếu xe", start:25200, end:36000 },
  oversupply: { label:"Dư xe", start:46800, end:57600 },
} as const;
export function secondsToTime(value: number): string {
  const v=Math.round(value), h=Math.floor(v/3600),m=Math.floor(v%3600/60),s=v%60;
  return [h,m,s].map(x=>String(x).padStart(2,"0")).join(":");
}
export function timeToSeconds(value: string): number {
  if(!/^\d{1,3}:\d{2}(:\d{2})?$/.test(value)) throw new Error("Thời gian cần dạng HH:MM hoặc HH:MM:SS.");
  const [h,m,s=0]=value.split(":").map(Number);
  if(m>=60||s>=60)throw new Error("Phút và giây phải nhỏ hơn 60.");
  return h*3600+m*60+s;
}
export function newScenario(): RunSpec {
  return { name:"", scenario:{ name:"", network:{kind:"grid",width_m:8000,height_m:8000,spacing_m:250,speed_kmh:25},zones:{kind:"square",cell_m:1000},source:{kind:"synthetic",t_start:25200,t_end:25800,demand_per_hour:200},seed:0 },fleets:[],vehicle_types:[],seed:null,crn_seed:null,sim_config:{timeseries_interval_s:60},outputs:{event_log:"csv.gz"} };
}
export function sourceParameters(source: Source): Record<string,unknown> { return source.kind==="preset" ? source.overrides??{} : source; }
export function withSourceParameters(source: Source, changes: Record<string,unknown>): Source {
  return source.kind==="preset"?{...source,overrides:{...source.overrides,...changes}}:{...source,...changes};
}
export function changeSource(source:Source,kind:string):Source {
  if(source.kind===kind)return source;
  const p=sourceParameters(source);
  const start=typeof p.t_start==="number"?p.t_start:25200, end=typeof p.t_end==="number"?p.t_end:25800;
  return {kind,...(kind==="preset"?{preset:"weekday_am_peak",demand_per_hour:200,overrides:{t_start:start,t_end:end}}:{t_start:start,t_end:end,demand_per_hour:source.demand_per_hour??200})};
}
export function selectFleet(spec:RunSpec,fleet:Entity<Fleet>,selected:boolean):RunSpec {
  const matches=(x:Ref|Fleet)=>"ref" in x&&(x.ref===fleet.id||x.ref===fleet.name);
  return {...spec,fleets:selected?[...(spec.fleets??[]).filter(x=>!matches(x)),{ref:fleet.id}]:(spec.fleets??[]).filter(x=>!matches(x))};
}
export function scenarioPayload(spec:RunSpec):RunSpec {
  const next=structuredClone(spec);
  next.scenario.name=next.scenario.name.trim(); next.name=next.name.trim()||next.scenario.name;
  // Preserve hidden configuration, including charging_stations and inline entities.
  // Public input must never acquire the legacy policy fields from a resolved snapshot.
  delete next.policy_group;
  return next;
}
