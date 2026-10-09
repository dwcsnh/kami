import { describe, expect, it, vi } from "vitest";
import { acceptFrame, emptyLive, MAX_LIVE_ROWS, startQueued, visibleMetric } from "./runState";
describe("run lifecycle",()=>{
  it("retains the queued snapshot id when start is busy, and retries it",async()=>{
    const queue=vi.fn().mockResolvedValue({id:19}),start=vi.fn().mockRejectedValueOnce(new Error("409")).mockResolvedValueOnce({}),retain=vi.fn();
    await expect(startQueued(queue,start,undefined,retain)).rejects.toThrow("409");
    expect(retain).toHaveBeenCalledWith(19);
    await expect(startQueued(queue,start,19,retain)).resolves.toBe(19);
    expect(queue).toHaveBeenCalledTimes(1);expect(start).toHaveBeenLastCalledWith(19);
  });
  it("isolates runs, deduplicates reconnect rows, preserves null and marks resync gaps",()=>{
    let s=emptyLive(2);
    expect(acceptFrame(s,"metric",{run_id:1,row:{t:1,a:4}})).toBe(s);
    s=acceptFrame(s,"metric",{run_id:2,row:{t:1,a:null}});
    s=acceptFrame(s,"metric",{run_id:2,row:{t:1,a:2}});
    expect(s.rows).toEqual([{t:1,a:2}]);expect(acceptFrame(s,"resync",{}).gap).toBe(true);
    expect(acceptFrame(s,"terminal",{status:"succeeded"}).status).toBe("succeeded");
  });
  it("bounds live memory and drops invalid metric frames",()=>{
    const s={...emptyLive(1),rows:Array.from({length:MAX_LIVE_ROWS},(_,t)=>({t,a:1}))};
    const next=acceptFrame(s,"metric",{row:{t:MAX_LIVE_ROWS,a:2}});
    expect(next.rows).toHaveLength(MAX_LIVE_ROWS);expect(next.trimmed).toBe(true);expect(next.rows[0].t).toBe(1);
    expect(acceptFrame(s,"metric",{row:{t:NaN}})).toBe(s);
  });
  it("does not expose legacy pooling metrics",()=>{expect(visibleMetric("rider.pool_rate")).toBe(false);expect(visibleMetric("platform.pooled_jobs")).toBe(false);expect(visibleMetric("rider.wait_mean")).toBe(true);});
});
