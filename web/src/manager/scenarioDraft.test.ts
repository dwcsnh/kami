import { describe, expect, it } from "vitest";
import { changeSource, newScenario, scenarioPayload, secondsToTime, selectFleet, timeToSeconds, withSourceParameters } from "./scenarioDraft";
import type { RunSpec } from "./types";
describe("scenario form round trip",()=>{
  it("preserves source details, inline entities and deferred charging data while editing",()=>{
    const spec:RunSpec={...newScenario(),name:" x ",charging_stations:[{ref:7}],behavior:{preset:"employed_drivers"},fleets:[{name:"inline",composition:[{vehicle_type:"car",count:3}]}],scenario:{name:" s ",source:{kind:"csv",file:"demand.csv",time_col:"time"},traffic:{congestion:{kind:"file",file:"traffic.csv"}}}};
    const actual=scenarioPayload(spec);
    expect(actual.scenario.name).toBe("s");expect(actual.name).toBe("x");
    expect(actual.charging_stations).toEqual([{ref:7}]);expect(actual.scenario.source).toEqual(spec.scenario.source);expect(actual.fleets).toEqual(spec.fleets);expect(actual.behavior).toEqual(spec.behavior);
    expect(spec.name).toBe(" x ");expect(newScenario().charging_stations).toBeUndefined();
  });
  it("changes preset parameters without losing preset or demand",()=>{
    const source={kind:"preset",preset:"rain",demand_per_hour:12,overrides:{warmup_s:10}};
    expect(withSourceParameters(source,{t_start:10})).toEqual({...source,overrides:{warmup_s:10,t_start:10}});
    expect(changeSource({kind:"csv",file:"old"},"synthetic")).not.toHaveProperty("file");
  });
  it("supports named and numeric fleet refs without silently changing inline fleets",()=>{
    const f={id:4,name:"stored",spec:{name:"stored",composition:[]}};
    let s:RunSpec={...newScenario(),fleets:[{ref:"stored"},{name:"inline",composition:[]}]};
    s=selectFleet(s,f,true);expect(s.fleets).toEqual([{name:"inline",composition:[]},{ref:4}]);
    expect(selectFleet(s,f,false).fleets).toEqual([{name:"inline",composition:[]}]);
  });
  it("converts simulation seconds without timezone conversions",()=>{
    expect(timeToSeconds("07:15:30")).toBe(26130);expect(secondsToTime(26130)).toBe("07:15:30");
    expect(timeToSeconds("24:00")).toBe(86400);expect(()=>timeToSeconds("07:80")).toThrow();
  });
});
