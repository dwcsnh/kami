import { expect, it } from "vitest";
import { Replay } from "./replay";
import type { ReplayDocs } from "./types";

const pair={id:1,rider_ids:[1,2],driver_id:8,created_t:0,closed_t:190,reason:null,stops:[],predicted_pickup:{1:0,2:40},predicted_dropoff:{1:160,2:190},pickups:{1:0,2:40},dropoffs:{1:160,2:190},predicted_overlap_s:120,actual_overlap_s:120,actual_shared:true,overlap_start:40,overlap_end:160};
function docs(shared:boolean):ReplayDocs {
  return {manifest:{schema_version:1,kind:"kami.replay",kami_version:"0.1",coords:"xy",run:{},area:null,bounds:null,time:{start:0,end:200},states:[],fleets:{},counts:{vehicles:0,segments:0,points:0,events:0,metric_rows:0},files:{} as ReplayDocs["manifest"]["files"],simplify:{dist_m:1,dt_s:.5},...(shared?{shared:{version:1,fare_factor:.7,pairs:[pair],riders:[]}}:{})},vehicles:[],trips:{vehicle:[],state:[],rider:[],t0:[],t1:[],dist_m:[],path:[],ts:[]},events:{t:[],type:[],rider:[],vehicle:[],lon:[],lat:[]},metrics:{t:[],series:{},interval_s:null}};
}
it("reads optional shared metadata with exact 0/1/2 rider boundaries",()=>{
  const rp=new Replay(docs(true));
  for(const [t,count] of [[-1,0],[0,1],[39,1],[40,2],[159,2],[160,1],[190,0]])expect(rp.sharedOnboardAt(1,t)).toHaveLength(count);
  expect(rp.sharedPairAt(8,50)?.id).toBe(1);expect(rp.sharedPairAt(8,191)).toBeUndefined();
  expect(new Replay(docs(false)).sharedPairAt(8,50)).toBeUndefined();
});
