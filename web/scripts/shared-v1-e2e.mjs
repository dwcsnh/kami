// Sprint 12: Shared V1 browser + real service/worker, isolated DB. CHROME/PYTHON may override executable paths.
import { strict as assert } from "node:assert";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "node:net";
import { chromium } from "playwright-core";
const web=resolve(dirname(fileURLToPath(import.meta.url)),".."),root=resolve(web,"..");
const evidence=resolve(process.env.KAMI_E2E_EVIDENCE_DIR||join(root,".runtime","shared-v1","e2e")),shots=join(root,"docs","engine","img","shared-v1");
await mkdir(evidence,{recursive:true});await mkdir(shots,{recursive:true});
const temp=await mkdtemp(join(tmpdir(),"kami-manager-"));
const apiPort=Number(process.env.KAMI_E2E_API_PORT||8109),webPort=Number(process.env.KAMI_E2E_WEB_PORT||3149);
const origin="http://127.0.0.1:"+webPort,backend="http://127.0.0.1:"+apiPort;
const chrome=process.env.CHROME||["C:/Program Files/Google/Chrome/Application/chrome.exe","/usr/bin/google-chrome"].find(existsSync);
assert(chrome,"Set CHROME to a system Chrome executable.");
for(const port of [apiPort,webPort])await new Promise((ok,fail)=>{const s=createServer();s.once("error",fail);s.listen(port,"127.0.0.1",()=>s.close(ok));});
const env={...process.env,KAMI_SERVICE_URL:backend,PYTHONUTF8:"1"};
if(process.env.KAMI_TEST_PYTHONPATH)env.PYTHONPATH=process.env.KAMI_TEST_PYTHONPATH+(env.PYTHONPATH?delimiter+env.PYTHONPATH:"");
const children=new Set(),checks=[],consoleErrors=[];
let browser,service,next;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function launch(exe,args,cwd,label) {
  const child=spawn(exe,args,{cwd,env,windowsHide:true,stdio:["ignore","pipe","pipe"]});children.add(child);
  let text="";child.stdout.on("data",b=>{text+=b;});child.stderr.on("data",b=>{text+=b;});
  child.on("exit",()=>{children.delete(child);void writeFile(join(evidence,label+".log"),text);});
  child.on("error",e=>{text+=String(e);});
  child.log=()=>text;return child;
}
async function finished(child,timeout=120000) {
  const start=Date.now();while(child.exitCode===null&&child.signalCode===null){if(Date.now()-start>timeout)throw new Error("Process timeout: "+child.log());await delay(100);}
  assert.equal(child.exitCode,0,child.log());
}
async function ready(url,child) {
  const start=Date.now();
  while(Date.now()-start<90000){
    if(child.exitCode!==null)throw new Error("Server exited: "+child.log());
    try{const r=await fetch(url,{signal:AbortSignal.timeout(1000)});if(r.ok)return;}catch{}
    await delay(200);
  }
  throw new Error("Server not ready: "+url+"\n"+child.log());
}
async function stop(child){
  if(!child||child.exitCode!==null||child.signalCode!==null)return;
  if(child.stopFile)await writeFile(child.stopFile,"stop");
  for(let i=0;i<30&&child.exitCode===null;i++)await delay(100);
  if(child.exitCode!==null)return;
  child.kill("SIGTERM");
  await Promise.race([new Promise(r=>child.once("exit",r)),delay(3000)]);
  if(child.exitCode===null&&child.signalCode===null)throw new Error("Test-owned process did not stop: "+child.pid);
}
async function get(path){const r=await fetch(origin+"/api/v1"+path);assert(r.ok,path+" "+r.status);return r.json();}
async function waitStatus(id,status){const start=Date.now();while(Date.now()-start<60000){const d=await get("/runs/"+id);if(d.status===status)return d;if(["failed","cancelled"].includes(d.status)&&d.status!==status)throw new Error(JSON.stringify(d));await delay(150);}throw new Error("Run status timeout "+id);}
function record(name){checks.push(name);console.log("PASS "+name);}
try {
  if(!process.env.KAMI_E2E_SKIP_BUILD){const build=launch(process.execPath,["node_modules/next/dist/bin/next","build"],web,"build");await finished(build);}
  service=launch(process.env.PYTHON||"python",["web/scripts/manager-test-host.py","--db",join(temp,"kami.db"),"--artifacts",join(temp,"runs"),"--port",String(apiPort),"--stop-file",join(temp,"stop")],root,"service");service.stopFile=join(temp,"stop");
  await ready(backend+"/api/v1/health",service);
  next=launch(process.execPath,["node_modules/next/dist/bin/next","start","--hostname","127.0.0.1","--port",String(webPort)],web,"next");
  await ready(origin+"/scenarios",next);
  const health=await get("/health");assert.deepEqual(health.capabilities.shared_ride_versions,[1]);
  async function post(path,body){const r=await fetch(origin+"/api/v1"+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json();}
  // Setup real stored fleet; scenario creation and editing are done through the form.
  const vehicle=await post("/vehicle-types",{name:"Shared car",group:"car",seats:4});
  const fleet=await post("/fleets",{name:"Shared fleet",composition:[{vehicle_type:"Shared car",count:8}]});
  browser=await chromium.launch({executablePath:chrome,headless:true,args:["--disable-dev-shm-usage"]});
  const page=await browser.newPage({viewport:{width:1440,height:900}});page.on("pageerror",e=>consoleErrors.push(String(e)));
  await page.goto(origin+"/scenarios");
  await page.getByRole("button",{name:"+ Tạo kịch bản",exact:true}).click();
  await page.getByLabel("Tên kịch bản",{exact:true}).fill("Shared E2E");
  await page.getByLabel("Shared fleet · 8 xe",{exact:true}).check();
  await page.getByRole("switch",{name:"Bật Shared ride V1",exact:true}).click();
  await page.getByLabel("Tỷ lệ Shared Only",{exact:true}).fill("1");await page.getByLabel("Tỷ lệ Exclusive Only",{exact:true}).fill("1");
  assert.equal(await page.getByLabel("Hạn đón tổng (phút)",{exact:true}).inputValue(),"10");
  assert.equal(await page.getByLabel("Phần tăng trên xe tối đa (phút)",{exact:true}).inputValue(),"7.5");
  await page.getByLabel("Bán kính ứng viên (m)",{exact:true}).fill("500");
  await page.getByLabel("Hạn đón tổng (phút)",{exact:true}).scrollIntoViewIfNeeded();
  await page.screenshot({path:join(shots,"form-1440.png"),fullPage:true});
  await page.getByRole("button",{name:"Lưu kịch bản",exact:true}).click();await page.getByRole("button",{name:"Chạy Shared E2E",exact:true}).waitFor();
  const scenario=(await get("/scenarios"))[0],cfg=scenario.spec.sim_config.shared_ride;
  assert.equal(cfg.max_pickup_wait_s,600);assert.equal(cfg.max_shared_extra_ride_s,450);assert.equal(cfg.fare_factor,.7);assert.equal(cfg.preference_weights.shared_only,.5);
  record("Shared form saves 600/450 seconds and two normalized weights without JSON input");
  const queued=page.waitForResponse(r=>r.url().endsWith("/api/v1/runs")&&r.request().method()==="POST");
  await page.getByRole("button",{name:"Chạy Shared E2E",exact:true}).click();const run=(await (await queued).json()).id;await waitStatus(run,"succeeded");
  const detail=await get("/runs/"+run),summary=(await get("/runs/"+run+"/metrics")).summary;
  assert(summary["shared.shared_only.booked"]>0);assert(summary["shared.exclusive_only.booked"]>0);
  await page.goto(origin+"/metrics?run="+run);await page.locator('[data-metric="shared.planned_pairs"]').waitFor();
  for(const [key,value] of Object.entries(summary).filter(([key])=>key.startsWith("shared."))){assert.equal(await page.locator('[data-metric="'+key+'"] [data-value]').getAttribute("data-value"),value===null?"":String(value));}
  await page.screenshot({path:join(shots,"results-1440.png"),fullPage:true});await page.reload();await page.locator('[data-metric="shared.planned_pairs"]').waitFor();
  record("Real worker summary equals persisted API and manager cells after reload");
  await page.goto(origin+"/scenarios");await page.getByRole("button",{name:"Sửa Shared E2E",exact:true}).click();
  await page.getByLabel("Hạn đón tổng (phút)",{exact:true}).fill("12");await page.getByRole("button",{name:"Lưu kịch bản",exact:true}).click();await page.getByRole("button",{name:"Chạy Shared E2E",exact:true}).waitFor();
  assert.deepEqual((await get("/runs/"+run)).run_spec,detail.run_spec);
  assert.equal((await get("/scenarios"))[0].spec.sim_config.shared_ride.max_pickup_wait_s,720);
  record("Scenario editing preserves completed run snapshot");
  // A second real worker run exercises an actual two-rider shared service on Hanoi roads.
  const demoSpec=JSON.parse(await readFile(join(root,"scenarios","shared","v1-demo.json"),"utf8"));
  demoSpec.scenario.source.file=join(root,demoSpec.scenario.source.file);
  const demoRun=(await post("/runs",{spec:demoSpec})).id;
  await post("/runs/"+demoRun+"/start",{});await waitStatus(demoRun,"succeeded");
  const demoSummary=(await get("/runs/"+demoRun+"/metrics")).summary;
  assert(demoSummary["shared.actual_pairs"]>0);assert(demoSummary["shared.shared_only.served"]>=2);
  assert.equal(demoSummary["shared.shared_only.gmv"],demoSummary["shared.shared_only.payout"]+demoSummary["shared.shared_only.platform_fee"]);
  await page.goto(origin+"/metrics?run="+demoRun);await page.locator('[data-metric="shared.actual_pairs"]').waitFor();
  assert.equal(await page.locator('[data-metric="shared.actual_pairs"] [data-value]').getAttribute("data-value"),String(demoSummary["shared.actual_pairs"]));
  await page.screenshot({path:join(shots,"results-shared-served-1440.png"),fullPage:true});
  record("Real Hanoi worker serves shared pairs and manager shows persisted overlap and financial totals");
  // The default visualizer now demonstrates the full shared lifecycle, with distinct moving stops.
  const walkthrough=JSON.parse(await readFile(join(web,"public","fixtures","shared_v1_walkthrough","manifest.json"),"utf8"));
  const journey=walkthrough.shared.pairs[0];
  await page.goto(origin+"/visualizer?panel=0");
  await page.getByRole("button",{name:"Xem từ đầu · 10×",exact:true}).click();
  const watchState=await page.evaluate(()=>{
    const st=window.__kami.store.getState();return {playing:st.playing,speed:st.speed,showShared:st.showRequests.shared_only};
  });
  assert.deepEqual(watchState,{playing:true,speed:10,showShared:true});
  await page.evaluate(()=>window.__kami.store.getState().setPlaying(false));
  await page.getByText("Các mốc đặt, ghép, đón và trả",{exact:true}).click();
  const flow=[
    ["Khách #1 đặt Shared","Chờ hệ thống ghép · 1/2",1,0],
    ["Khách #2 đặt Shared","Chờ hệ thống ghép · 2/2",2,0],
    ["Hệ thống ghép cặp, xe đi đón","Đi đón khách #2 · 0/2",2,0],
    ["Đón khách #2","Đi đón khách #1 · 1/2",1,1],
    ["Đón khách #1","Hai khách trên xe · Đang đi chung",0,2],
    ["Trả khách #2","Đi trả khách #1 · 1/2",0,1],
    ["Trả khách #1","Đã trả hết khách · Hoàn tất",0,0],
  ];
  for(const [label,stage,waiting,onboard] of flow){
    await page.getByRole("button",{name:new RegExp(label)}).click();
    await page.getByTestId("shared-journey-stage").filter({hasText:stage}).waitFor();
    await page.waitForFunction(({waiting,onboard,pairId})=>{
      const layers=window.__kamiMapLayers,st=window.__kami.store.getState(),rp=window.__kami.replay;
      return layers?.find(l=>l.id==="requests-shared_only")?.props.data.length===waiting&&rp.sharedOnboardAt(pairId,st.t).length===onboard;
    },{waiting,onboard,pairId:journey.id});
  }
  assert.equal(new Set(journey.stops.map(s=>s.loc)).size,4);
  await page.getByRole("button",{name:/Hệ thống ghép cặp, xe đi đón/}).click();
  await page.getByText("Cặp #"+journey.id+" · 0/2 khách trên xe",{exact:true}).waitFor();
  await page.waitForFunction(()=>window.__kamiMapLayers?.find(l=>l.id==="pair-stop-labels")?.state?.numInstances>0);
  await page.screenshot({path:join(shots,"walkthrough-matched-1440.png"),fullPage:true});
  record("Default Shared walkthrough: two bookings, waiting, match, two distinct pickups and two distinct dropoffs through UI controls");
  const manifest=JSON.parse(await readFile(join(web,"public","fixtures","shared_v1_demo","manifest.json"),"utf8"));
  const pair=manifest.shared.pairs.find(p=>p.actual_shared);assert(pair);
  for(const width of [1280,1440]){
    await page.setViewportSize({width,height:width===1280?800:900});
    for(const [name,t,count] of [["before",pair.created_t-1,0],["one",Math.min(...Object.values(pair.pickups)),1],["overlap",pair.overlap_start+1,2],["after",pair.overlap_end+1,1]]){
      await page.goto(origin+"/visualizer?replay=/fixtures/shared_v1_demo&select="+pair.driver_id+"&t="+t+"&panel=0");
      await page.waitForFunction(()=>Boolean(window.__kami));
      const actual=await page.evaluate(({id,t})=>window.__kami.replay.sharedOnboardAt(id,t).length,{id:pair.id,t});
      assert.equal(actual,count);
      if(name==="overlap")await page.getByText("Cặp #"+pair.id+" · 2/2 khách trên xe",{exact:true}).waitFor();
      await page.waitForFunction(()=>window.__kamiMapIdle===true,null,{timeout:12000}).catch(()=>{});
      await page.screenshot({path:join(shots,`replay-${name}-${width}.png`),fullPage:true});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
  }
  record("Hanoi replay pair/stops/0-1-2 onboard milestones at 1280 and 1440 pixels");
  // Verify the rendered deck.gl data, not only store flags: show shared vehicles alone.
  await page.goto(origin+"/visualizer?replay=/fixtures/shared_v1_demo&t="+(pair.overlap_start+1)+"&panel=0");
  await page.waitForFunction(()=>Boolean(window.__kamiMapLayers));
  for(const st of manifest.states)await page.getByRole("button",{name:new RegExp("^"+st.label)}).click();
  await page.waitForFunction(()=>{
    const layers=window.__kamiMapLayers,vehicles=layers.find(l=>l.id==="vehicles");
    return vehicles.props.data.length>0&&layers.filter(l=>l.id.startsWith("trail-")).every(l=>l.id==="trail-shared");
  });
  await page.getByRole("button",{name:/^Xe share/}).click();
  await page.waitForFunction(()=>window.__kamiMapLayers.find(l=>l.id==="vehicles").props.data.length===0);
  await page.getByRole("button",{name:/^Xe share/}).focus();await page.keyboard.press("Space");
  await page.waitForFunction(()=>window.__kamiMapLayers.find(l=>l.id==="vehicles").props.data.length>0);
  await page.screenshot({path:join(shots,"filters-shared-only-1440.png"),fullPage:true});
  // Find a real point in time with both request types waiting, including an Exclusive pickup delay.
  const candidates=manifest.shared.riders.filter(r=>r.booked_t!==null).map(r=>r.booked_t+1);
  const waitingAt=t=>manifest.shared.riders.filter(r=>r.booked_t!==null&&r.booked_t<=t&&t<Math.min(r.pickup_t??Infinity,r.cancel_t??Infinity));
  const requestTime=candidates.find(t=>["shared_only","exclusive_only"].every(pref=>waitingAt(t).some(r=>r.service_preference===pref)));
  assert(requestTime!==undefined);
  await page.evaluate(t=>window.__kami.store.getState().seek(t),requestTime);
  for(const [pref,label] of [["shared_only","Shared"],["exclusive_only","Exclusive"]]){
    await page.getByRole("button",{name:new RegExp("^Đặt "+label)}).click();
    await page.waitForFunction(pref=>window.__kamiMapLayers.some(l=>l.id==="requests-"+pref),pref);
    const riders=await page.evaluate(pref=>window.__kamiMapLayers.find(l=>l.id==="requests-"+pref).props.data.map(r=>r.rider),pref);
    assert.deepEqual(riders.sort((a,b)=>a-b),waitingAt(requestTime).filter(r=>r.service_preference===pref).map(r=>r.id).sort((a,b)=>a-b));
    // TextLayer must really initialize its glyphs, not merely expose a getText prop.
    await page.waitForFunction(pref=>{
      const label=window.__kamiMapLayers.find(l=>l.id==="requests-"+pref+"-labels");
      return label?.state?.numInstances===label.props.data.length&&label.state.numInstances>0;
    },pref);
  }
  await page.screenshot({path:join(shots,"filters-requests-1440.png"),fullPage:true});
  await page.setViewportSize({width:1280,height:800});
  const exclusiveFilter=page.getByRole("button",{name:/^Đặt Exclusive/});
  await exclusiveFilter.scrollIntoViewIfNeeded();
  const filterBounds=await exclusiveFilter.boundingBox(),playbackBounds=await page.getByLabel("Điều khiển phát lại",{exact:true}).boundingBox();
  assert(filterBounds&&playbackBounds&&filterBounds.y+filterBounds.height<=playbackBounds.y);
  await page.getByRole("button",{name:"Căn khung khu vực",exact:true}).click();
  await page.waitForFunction(()=>!window.__kamiMap.isMoving());
  await page.screenshot({path:join(shots,"filters-requests-1280.png"),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.getByRole("button",{name:/^Đặt Shared/}).click();
  await page.waitForFunction(()=>!window.__kamiMapLayers.some(l=>l.id==="requests-shared_only")&&window.__kamiMapLayers.some(l=>l.id==="requests-exclusive_only"));
  // Seeking forward past pickup/cancel removes markers; seeking back restores the same real bookings.
  await page.evaluate(()=>window.__kami.store.getState().seek(window.__kami.replay.end));
  await page.waitForFunction(()=>window.__kamiMapLayers.find(l=>l.id==="requests-exclusive_only").props.data.length===0);
  await page.evaluate(t=>window.__kami.store.getState().seek(t),requestTime);
  await page.waitForFunction(()=>window.__kamiMapLayers.find(l=>l.id==="requests-exclusive_only").props.data.length>0);
  await page.getByRole("button",{name:/^Đặt Exclusive/}).click();
  await page.waitForFunction(()=>!window.__kamiMapLayers.some(l=>l.id.startsWith("requests-")));
  record("Shared-only vehicles/trails, keyboard filter and independent real Shared/Exclusive waiting markers");
  assert.deepEqual(consoleErrors,[]);
  await writeFile(join(evidence,"result.json"),JSON.stringify({ok:true,checks,run,summary,demoRun,demoSummary,shots,temp},null,2));console.log("Shared V1 E2E complete");
}catch(e){if(browser){const page=browser.contexts()[0]?.pages()[0];await page?.screenshot({path:join(evidence,"failure.png"),fullPage:true}).catch(()=>{});}await writeFile(join(evidence,"result.json"),JSON.stringify({ok:false,error:String(e),checks,consoleErrors,temp},null,2));throw e;}
finally{await browser?.close();for(const child of [...children])await stop(child);}
