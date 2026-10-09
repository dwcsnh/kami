import { describe, expect, it } from "vitest";
import { minutesToSeconds, secondsToMinutes, sharedDefaults, sharedDraft, validateShared } from "./sharedDraft";
import { scenarioPayload, newScenario } from "./scenarioDraft";
import { metricLabel, metricUnit } from "./metricFormat";
describe("Shared ride V1 form",()=>{
  it("round trips 10 and 7.5 minutes and preserves hidden config",()=>{
    expect(minutesToSeconds(10)).toBe(600);expect(minutesToSeconds(7.5)).toBe(450);expect(secondsToMinutes(450)).toBe(7.5);
    const spec={...newScenario(),sim_config:{fare:{take_rate:.2},shared_ride:sharedDefaults()},charging_stations:[{ref:4}]};
    expect(scenarioPayload(spec).sim_config).toEqual(spec.sim_config);expect(scenarioPayload(spec).charging_stations).toEqual([{ref:4}]);
    expect(sharedDraft({...sharedDefaults(),enabled:false}).max_pickup_wait_s).toBe(600);
  });
  it("validates independent bounds and exactly two weights",()=>{
    expect(()=>validateShared(sharedDefaults())).not.toThrow();
    for(const patch of [{max_pickup_wait_s:0},{max_shared_extra_ride_s:-1},{candidate_radius_m:Infinity},{preference_weights:{shared_only:0,exclusive_only:0}}])expect(()=>validateShared({...sharedDefaults(),...patch})).toThrow();
    expect(()=>validateShared({...sharedDefaults(),max_shared_extra_ride_s:0})).not.toThrow();
  });
  it("labels cohort metric units",()=>{
    expect(metricUnit("shared.shared_only.extra_ride_p95")).toBe("phút");expect(metricUnit("shared.shared_only.payout")).toBe("VND");
    expect(metricLabel("shared.shared_only.served")).toBe("Shared Only · Hoàn thành");
  });
});
