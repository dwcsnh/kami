// Sprint 09 A: browser + real service/worker, isolated DB. CHROME/PYTHON may override executable paths.
import { strict as assert } from "node:assert";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "node:net";
import { chromium } from "playwright-core";
const web=resolve(dirname(fileURLToPath(import.meta.url)),".."),root=resolve(web,"..");
const evidence=resolve(process.env.KAMI_E2E_EVIDENCE_DIR||join(root,".runtime","sprint09","e2e")),shots=join(root,"docs","engine","img","manager","redesign");
await mkdir(evidence,{recursive:true});await mkdir(shots,{recursive:true});
const temp=await mkdtemp(join(tmpdir(),"kami-manager-"));
const apiPort=Number(process.env.KAMI_E2E_API_PORT||8099),webPort=Number(process.env.KAMI_E2E_WEB_PORT||3139);
const origin="http://127.0.0.1:"+webPort,backend="http://127.0.0.1:"+apiPort;
const chrome=process.env.CHROME||["C:/Program Files/Google/Chrome/Application/chrome.exe","/usr/bin/google-chrome"].find(existsSync);
assert(chrome,"Set CHROME to a system Chrome executable.");
for(const port of [apiPort,webPort])await new Promise((ok,fail)=>{const s=createServer();s.once("error",fail);s.listen(port,"127.0.0.1",()=>s.close(ok));});
const env={...process.env,KAMI_SERVICE_URL:backend,PYTHONUTF8:"1"};
if(process.env.KAMI_TEST_PYTHONPATH)env.PYTHONPATH=process.env.KAMI_TEST_PYTHONPATH+(env.PYTHONPATH?";"+env.PYTHONPATH:"");
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
  service=launch(process.env.PYTHON||"python",["web/scripts/manager-test-host.py","--db",join(temp,"kami.db"),"--artifacts",join(temp,"runs"),"--port",String(apiPort),"--stop-file",join(temp,"stop-first")],root,"service");service.stopFile=join(temp,"stop-first");
  await ready(backend+"/api/v1/health",service);
  next=launch(process.execPath,["node_modules/next/dist/bin/next",process.env.KAMI_E2E_DEV?"dev":"start","--hostname","127.0.0.1","--port",String(webPort)],web,"next");
  await ready(origin+"/api/v1/health",next);record("same-origin proxy health");
  browser=await chromium.launch({executablePath:chrome,headless:true,args:["--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"]});
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  let streamRequests=0;page.on("request",r=>{if(r.resourceType()==="eventsource")streamRequests++;});
  page.on("pageerror",e=>consoleErrors.push(String(e)));
  let releaseScenario;
  const scenarioGate=new Promise(resolve=>{releaseScenario=resolve;});
  const holdScenario=async route=>{await scenarioGate;await route.continue();};
  await page.route("**/api/v1/scenarios",holdScenario);
  await page.goto(origin+"/scenarios");
  const countLoading=page.getByRole("status",{name:"Đang tải Kịch bản đã lưu",exact:true});
  await countLoading.waitFor();
  assert.equal(await countLoading.locator('[data-slot="skeleton"]').evaluate(el=>getComputedStyle(el).animationName),"workspace-pulse");
  assert.equal(await page.getByRole("status",{name:"Đang tải kịch bản",exact:true}).count(),1);
  await page.screenshot({path:join(shots,"loading-shared-1440.png"),fullPage:true});
  await page.emulateMedia({reducedMotion:"reduce"});
  assert.equal(await countLoading.locator('[data-slot="skeleton"]').evaluate(el=>getComputedStyle(el).animationName),"none");
  await page.emulateMedia({reducedMotion:"no-preference"});
  releaseScenario();await countLoading.waitFor({state:"hidden"});
  await page.unroute("**/api/v1/scenarios",holdScenario);
  record("shared skeleton waits for actual API and respects reduced motion");
  await page.goto(origin+"/fleets");
  const backgroundBefore=await page.getByRole("heading",{name:"Đội xe & loại xe",exact:true}).boundingBox();
  await page.getByRole("button",{name:"+ Thêm loại xe",exact:true}).click();
  const vehicleModal=page.getByRole("dialog",{name:"Thêm loại xe",exact:true});
  await vehicleModal.waitFor();
  const backgroundDuring=await page.getByRole("heading",{name:"Đội xe & loại xe",exact:true,includeHidden:true}).boundingBox();
  assert.equal(backgroundBefore.y,backgroundDuring.y);
  await page.getByLabel("Nhóm xe",{exact:true}).click();
  await page.getByRole("option",{name:"Xe máy",exact:true}).click();
  await page.getByLabel("Nhóm xe",{exact:true}).focus();await page.keyboard.press("Enter");
  await page.getByRole("listbox").waitFor();
  await page.waitForFunction(()=>document.activeElement?.getAttribute("data-value")==="bike");
  await page.keyboard.press("Home");
  await page.waitForFunction(()=>document.activeElement?.getAttribute("data-value")==="car");
  await page.keyboard.press("Enter");
  await page.waitForFunction(()=>document.querySelector('[role="combobox"]')?.textContent==="Ô tô");
  assert.equal(await page.getByLabel("Nhóm xe",{exact:true}).textContent(),"Ô tô");
  await page.screenshot({path:join(shots,"vehicle-modal-1440.png"),fullPage:true});
  await page.keyboard.press("Escape");await vehicleModal.waitFor({state:"hidden"});
  assert.equal(await page.locator(":focus").textContent(),"+ Thêm loại xe");
  await page.getByRole("button",{name:"+ Thêm loại xe",exact:true}).click();
  record("modal keeps page position; dropdown supports keyboard; Escape restores focus");
  await page.getByLabel("Tên loại xe",{exact:true}).fill("Car E2E");
  await page.getByLabel("Quãng đường tối đa (km)",{exact:true}).fill("300");
  await page.getByRole("button",{name:"Lưu loại xe",exact:true}).click();
  await page.getByRole("button",{name:"Sửa Car E2E",exact:true}).waitFor();
  await page.reload();await page.getByRole("button",{name:"Sửa Car E2E",exact:true}).waitFor();
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(":focus").textContent(),"Đến nội dung");
  await page.keyboard.press("Enter");
  assert.equal(await page.locator(":focus").getAttribute("id"),"manager-content");
  record("keyboard skip link moves focus to workspace content");
  assert.equal((await get("/vehicle-types"))[0].spec.range_km,300);
  record("vehicle CRUD persisted after reload");
  // Duplicate validation keeps every form value; close it explicitly afterwards.
  await page.getByRole("button",{name:"+ Thêm loại xe",exact:true}).click();
  await page.getByLabel("Tên loại xe",{exact:true}).fill("Car E2E");
  await page.getByRole("button",{name:"Lưu loại xe",exact:true}).click();
  await page.getByRole("alert").filter({hasText:"Chưa hoàn tất thao tác"}).waitFor();
  assert.equal(await page.getByLabel("Tên loại xe",{exact:true}).inputValue(),"Car E2E");
  await page.getByRole("button",{name:"Đóng form",exact:true}).click();record("conflict preserves draft");
  await page.getByRole("tab",{name:/^Fleet/}).click();
  await page.getByRole("button",{name:"+ Thêm fleet",exact:true}).click();
  await page.getByLabel("Tên fleet",{exact:true}).fill("Fleet E2E");
  await page.getByRole("button",{name:"+ Thêm thành phần",exact:true}).click();
  await page.getByLabel("Số lượng 1",{exact:true}).fill("20");
  await page.getByRole("button",{name:"Lưu fleet",exact:true}).click();
  await page.getByRole("button",{name:"Sửa Fleet E2E",exact:true}).waitFor();record("fleet CRUD through UI");
  await page.getByRole("searchbox",{name:"Tìm loại xe hoặc đội xe…"}).fill("không có đội xe này");
  await page.getByText("Không tìm thấy cấu hình.",{exact:false}).waitFor();
  await page.getByRole("searchbox",{name:"Tìm loại xe hoặc đội xe…"}).fill("fleet");
  await page.getByRole("button",{name:"Sửa Fleet E2E",exact:true}).waitFor();
  await page.getByRole("searchbox",{name:"Tìm loại xe hoặc đội xe…"}).fill("");
  record("fleet search filters actual saved entities");
  await page.screenshot({path:join(shots,"fleets-1440.png"),fullPage:true});
  assert.equal(await page.getByText("Trạm sạc",{exact:true}).count(),0);
  await page.getByRole("link",{name:"Kịch bản",exact:true}).click();
  await page.getByRole("button",{name:"+ Tạo kịch bản",exact:true}).click();
  await page.getByLabel("Tên kịch bản",{exact:true}).fill("Demo E2E");
  await page.getByLabel("Seed",{exact:true}).fill("2");
  await page.getByLabel("Giờ kết thúc",{exact:true}).fill("07:10:00");
  await page.getByLabel("Fleet E2E · 20 xe",{exact:true}).check();
  await page.getByLabel("Thời gian hoàn tất chuyến sau demand (giây)",{exact:true}).fill("60");
  const collection=page.getByRole("switch",{name:"Thu thập chuỗi thời gian",exact:true});
  await collection.click();
  assert(await page.getByLabel("Khoảng lấy metric (giây)",{exact:true}).isDisabled());
  await collection.click();
  assert(!(await page.getByLabel("Khoảng lấy metric (giây)",{exact:true}).isDisabled()));
  const track=await collection.boundingBox(),thumb=await collection.locator('[data-slot="switch-thumb"]').boundingBox();
  assert(thumb.x>=track.x&&thumb.x+thumb.width<=track.x+track.width,"switch thumb must remain inside track");
  await page.screenshot({path:join(shots,"switch-modal-1440.png"),fullPage:true});
  record("shadcn switch controls metric collection");
  await page.locator('[data-slot="dialog-content"] > div').last().evaluate(el=>el.scrollTo(0,0));
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  await page.screenshot({path:join(shots,'scenario-form-1440.png'),fullPage:true});
  await page.getByRole("button",{name:"Lưu kịch bản",exact:true}).click();
  await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).waitFor();
  const scenarios=await get("/scenarios"),scenario=scenarios[0];
  assert.equal(scenario.spec.fleets[0].ref,(await get("/fleets"))[0].id);
  assert.equal(scenario.spec.charging_stations.length,0);record("scenario form saves fleet ref without charging configuration");
  await page.getByRole("searchbox",{name:"Tìm kịch bản theo tên…"}).fill("không có kịch bản này");
  await page.getByText("Không tìm thấy kịch bản.",{exact:false}).waitFor();
  assert.equal(await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).count(),0);
  await page.getByRole("searchbox",{name:"Tìm kịch bản theo tên…"}).fill("demo");
  await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).waitFor();
  await page.getByRole("searchbox",{name:"Tìm kịch bản theo tên…"}).fill("");
  record("scenario search filters names and recovers from no results");
  await page.screenshot({path:join(shots,"scenarios-1440.png"),fullPage:true});
  async function startFromUI(){
    const queued=page.waitForResponse(r=>r.url().endsWith("/api/v1/runs")&&r.request().method()==="POST");
    await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).click();
    const run=await (await queued).json();
    return run.id;
  }
  const first=await startFromUI();
  await waitStatus(first,"succeeded");
  await page.goto(origin+"/metrics?run="+first);
  await page.locator('[data-metric="platform.trips"]').waitFor();
  const summary=(await get("/runs/"+first+"/metrics")).summary;
  for(const [key,value]of Object.entries(summary)){
    const cell=page.locator('[data-metric="'+key+'"] [data-value]');
    assert.equal(await cell.getAttribute("data-value"),value===null?"":String(value));
  }
  const downloadEvent=page.waitForEvent("download");await page.getByRole("button",{name:"CSV tổng hợp",exact:true}).click();
  const download=await downloadEvent;const csv=await readFile(await download.path(),"utf8");
  assert(csv.includes("platform.trips,"+summary["platform.trips"]));record("real worker completes; summary UI and CSV equal API");
  await page.screenshot({path:join(shots,"metrics-1440.png"),fullPage:true});
  await page.goto(origin+"/fleets");await page.getByRole("tab",{name:/^Fleet/}).click();
  await page.getByRole("button",{name:"Sửa Fleet E2E",exact:true}).click();await page.getByLabel("Số lượng 1",{exact:true}).fill("25");await page.getByRole("button",{name:"Lưu fleet",exact:true}).click();await page.getByRole("button",{name:"Sửa Fleet E2E",exact:true}).waitFor();
  assert.equal((await get("/runs/"+first)).run_spec.fleets[0].composition[0].count,20);record("fleet update preserves previous run snapshot");
  await page.goto(origin+"/scenarios");await page.getByRole("button",{name:"Sửa Demo E2E",exact:true}).click();
  await page.getByLabel("Seed",{exact:true}).fill("3");await page.getByRole("button",{name:"Lưu kịch bản",exact:true}).click();
  await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).waitFor();
  const second=await startFromUI();await waitStatus(second,"succeeded");
  assert.equal((await get("/runs/"+first)).seed,2);record("saved template edit leaves previous run snapshot immutable");
  await page.goto(origin+"/metrics");await page.getByRole("tab",{name:"So sánh các run",exact:true}).click();
  await page.getByLabel("Baseline",{exact:true}).click();
  await page.locator('[data-slot="select-item"][data-value="'+first+'"]').click();
  await page.getByLabel("#"+second+" · Demo E2E",{exact:true}).check();
  await page.getByRole("button",{name:"So sánh",exact:true}).click();
  await page.getByText("Seed/CRN không ghép cặp",{exact:true}).waitFor();
  const comparison=await get("/runs/compare?ids="+first+","+second);
  for(const metric of comparison.comparisons[0].metrics){
    const row=page.locator('[data-compare-metric="'+metric.metric+'"]');
    assert.equal(await row.locator("[data-delta]").getAttribute("data-delta"),metric.delta===null?"":String(metric.delta));
    assert.equal(await row.locator("[data-verdict]").getAttribute("data-verdict"),metric.verdict??"");
  }
  record("comparison delta, verdict and seed warning equal API");
  await page.screenshot({path:join(shots,"comparison-1440.png"),fullPage:true});
  // Graceful restart proves that SQLite, not a browser cache, owns configuration and results.
  await page.goto(origin+"/scenarios");await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).waitFor();
  await stop(service);
  await page.getByText("Mất kết nối backend",{exact:true}).waitFor();
  assert(await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).isDisabled());
  service=launch(process.env.PYTHON||"python",["web/scripts/manager-test-host.py","--db",join(temp,"kami.db"),"--artifacts",join(temp,"runs"),"--port",String(apiPort),"--stop-file",join(temp,"stop-second")],root,"service-restart");service.stopFile=join(temp,"stop-second");
  await ready(backend+"/api/v1/health",service);await page.reload();
  await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).waitFor();
  assert.equal((await get("/scenarios"))[0].spec.seed,3);
  assert.equal((await get("/runs/"+first+"/metrics")).summary["platform.trips"],summary["platform.trips"]);record("service restart retains SQLite entities and results; offline start blocked");
  // Long real run: show active banner on every page, receive SSE metric before terminal, cancel via UI.
  await page.getByRole("button",{name:"Sửa Demo E2E",exact:true}).click();
  await page.getByLabel("Giờ kết thúc",{exact:true}).fill("10:00:00");
  await page.getByLabel("Demand cơ sở (request/giờ)",{exact:true}).fill("12000");
  await page.getByRole("button",{name:"Lưu kịch bản",exact:true}).click();
  await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).waitFor();
  const long=await startFromUI();
  const streamAbort=new AbortController();
  const metricPromise=(async()=>{
    const response=await fetch(origin+"/api/v1/runs/"+long+"/stream",{signal:streamAbort.signal});
    assert(response.ok);const reader=response.body.getReader();let buffer="";
    const timer=setTimeout(()=>streamAbort.abort(),45000);
    try{while(true){const part=await reader.read();if(part.done)break;buffer+=new TextDecoder().decode(part.value);
      const frames=buffer.split("\n\n");buffer=frames.pop()??"";
      for(const frame of frames){if(frame.includes("event: metric")){const line=frame.split("\n").find(x=>x.startsWith("data: "));return JSON.parse(line.slice(6)).row;}if(frame.includes("event: terminal"))throw new Error("SSE terminated before metric");}
    }throw new Error("SSE ended without metric");}finally{clearTimeout(timer);await reader.cancel().catch(()=>{});streamAbort.abort();}
  })();
  metricPromise.catch(()=>{});
  await page.getByTestId("active-run").waitFor();
  const streamsBeforeNavigation=streamRequests;
  for(const label of ["Đội xe & loại xe","Kết quả & so sánh","Bản đồ mô phỏng","Kịch bản"]){await page.getByRole("navigation",{name:"Điều hướng chính"}).getByRole("link",{name:label,exact:true}).click();await page.getByTestId("active-run").waitFor();}
  assert(await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).isDisabled());
  assert.equal(streamRequests,streamsBeforeNavigation,"navigation duplicates EventSource");
  const liveRow=await metricPromise;
  assert.equal((await get("/runs/"+long)).status,"running");record("SSE metric arrives through production proxy while real run is running");
  await page.goto(origin+"/visualizer?run="+long);await page.getByText("Metric live tạm thời",{exact:false}).waitFor();
  assert.equal(await page.locator("canvas.mapboxgl-canvas").count(),0);
  await page.screenshot({path:join(shots,"run-live-metrics-1440.png"),fullPage:true});
  await page.getByRole("button",{name:"Huỷ run #"+long,exact:true}).click();await waitStatus(long,"cancelled");
  record("global banner across four pages, busy start lock and UI cancellation");
  assert(Number.isFinite(liveRow.t));
  await page.goto(origin+"/fleets");await page.getByRole("button",{name:"Xoá Car E2E",exact:true}).click();
  await page.getByRole("button",{name:"Giữ lại",exact:true}).click();assert.equal((await get("/vehicle-types")).length,1);record("delete confirmation cancellation sends no deletion");
  await page.getByRole("button",{name:"Xoá Car E2E",exact:true}).click();await page.getByRole("button",{name:"Xác nhận xoá",exact:true}).click();
  await page.getByRole("alert").filter({hasText:"Chưa hoàn tất thao tác"}).waitFor();assert.equal((await get("/vehicle-types")).length,1);record("in-use vehicle deletion reports conflict");
  await page.reload();await page.getByRole("button",{name:"Sửa Car E2E",exact:true}).click();await page.getByLabel("Quãng đường tối đa (km)",{exact:true}).fill("350");await page.getByRole("button",{name:"Lưu loại xe",exact:true}).click();await page.getByRole("button",{name:"Sửa Car E2E",exact:true}).waitFor();assert.equal((await get("/runs/"+first)).run_spec.vehicle_types[0].range_km,300);record("vehicle update keeps run snapshot immutable");
  await page.getByRole("button",{name:"+ Thêm loại xe",exact:true}).click();await page.getByLabel("Tên loại xe",{exact:true}).fill("Delete type");await page.getByRole("button",{name:"Lưu loại xe",exact:true}).click();await page.getByRole("button",{name:"Xoá Delete type",exact:true}).click();await page.getByRole("button",{name:"Xác nhận xoá",exact:true}).click();await page.getByRole("button",{name:"Xoá Delete type",exact:true}).waitFor({state:"hidden"});assert.equal((await get("/vehicle-types")).length,1);
  await page.getByRole("tab",{name:/^Fleet/}).click();await page.getByRole("button",{name:"+ Thêm fleet",exact:true}).click();await page.getByLabel("Tên fleet",{exact:true}).fill("Delete fleet");await page.getByRole("button",{name:"+ Thêm thành phần",exact:true}).click();await page.getByRole("button",{name:"Lưu fleet",exact:true}).click();await page.getByRole("button",{name:"Xoá Delete fleet",exact:true}).click();await page.getByRole("button",{name:"Xác nhận xoá",exact:true}).click();await page.getByRole("button",{name:"Xoá Delete fleet",exact:true}).waitFor({state:"hidden"});assert.equal((await get("/fleets")).length,1);record("successful vehicle and fleet deletion through UI");
  await page.goto(origin+"/scenarios");await page.getByRole("button",{name:"+ Tạo kịch bản",exact:true}).click();await page.getByLabel("Tên kịch bản",{exact:true}).fill("Delete scenario");await page.getByLabel("Fleet E2E · 25 xe",{exact:true}).check();await page.getByRole("button",{name:"Lưu kịch bản",exact:true}).click();await page.getByRole("button",{name:"Xoá Delete scenario",exact:true}).click();await page.getByRole("button",{name:"Xác nhận xoá",exact:true}).click();await page.getByRole("button",{name:"Xoá Delete scenario",exact:true}).waitFor({state:"hidden"});assert.equal((await get("/scenarios")).length,1);record("scenario deletion leaves run history intact");
  await page.getByRole("button",{name:"Sửa Demo E2E",exact:true}).click();page.once("dialog",d=>d.accept());await page.getByLabel("Mạng đường",{exact:true}).click();await page.locator('[data-slot="select-item"][data-value="road"]').click();await page.getByLabel("Tên mạng đường",{exact:true}).fill("missing_network_e2e");await page.getByRole("button",{name:"Lưu kịch bản",exact:true}).click();await page.getByRole("button",{name:"Chạy Demo E2E",exact:true}).waitFor();const failed=await startFromUI();await waitStatus(failed,"failed");await page.goto(origin+"/metrics?run="+failed);await page.getByRole("button",{name:"CSV tổng hợp",exact:true}).waitFor();assert(await page.getByRole("button",{name:"CSV tổng hợp",exact:true}).isDisabled());record("failed worker run shows no complete result export");
  await page.goto(origin+"/metrics?run=999999");await page.getByRole("alert").filter({hasText:"Chưa hoàn tất thao tác"}).waitFor();record("missing run renders a recoverable error");
  for(const width of [375,768,1280,1440]){
    await page.setViewportSize({width,height:width===1280?800:900});
    for(const route of ["scenarios","fleets","metrics"]){
      await page.goto(origin+"/"+route+(route==="metrics"?"?run="+first:""));await page.getByRole("heading",{level:1}).waitFor();
      if(route==="metrics")await page.locator('[data-metric="platform.trips"]').waitFor();
      else await page.getByRole("button",{name:route==="fleets"?"Sửa Car E2E":"Sửa Demo E2E",exact:true}).waitFor();
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),"page overflows "+route+" "+width);
      const navTargets=await page.getByRole("navigation",{name:"Điều hướng chính"}).getByRole("link").evaluateAll(links=>links.map(link=>({name:link.getAttribute("aria-label"),width:link.getBoundingClientRect().width,height:link.getBoundingClientRect().height})));
      assert(navTargets.every(link=>link.name&&link.width>=44&&link.height>=44),"navigation names or target sizes "+width);
      await page.screenshot({path:join(shots,route+"-"+width+".png"),fullPage:true});
    }
  }
  for(const width of [375,768,1440]){
    await page.setViewportSize({width,height:width===375?812:900});
    await page.goto(origin+"/scenarios");
    await page.getByRole("button",{name:"Sửa Demo E2E",exact:true}).click();
    const modal=page.getByRole("dialog",{name:"Chỉnh sửa kịch bản",exact:true});await modal.waitFor();
    const box=await modal.boundingBox();
    assert(box.x>=0&&box.x+box.width<=width&&box.y>=0&&box.y+box.height<=(width===375?812:900),"modal viewport "+width);
    assert.equal(await modal.evaluate(el=>el.scrollWidth<=el.clientWidth),true,"modal overflow "+width);
    await page.getByLabel("Nguồn demand",{exact:true}).click();
    const menu=page.getByRole("listbox");await menu.waitFor();
    const menuBox=await menu.boundingBox();assert(menuBox.x>=0&&menuBox.x+menuBox.width<=width,"dropdown viewport "+width);
    await page.screenshot({path:join(shots,"dropdown-modal-"+width+".png"),fullPage:true});
    await page.keyboard.press("Escape");await menu.waitFor({state:"hidden"});
    await page.keyboard.press("Escape");await modal.waitFor({state:"hidden"});
  }
  record("responsive modal and portalled dropdown remain inside viewport");
  await page.setViewportSize({width:1440,height:900});
  await page.goto(origin+"/visualizer?t=28800");
  await page.getByText("DEMO FIXTURE · không phải run trong database",{exact:true}).waitFor();
  await page.waitForFunction(()=>Boolean(window.__kami),null,{timeout:30000});
  const mapIdle=await page.waitForFunction(()=>window.__kamiMapIdle===true,null,{timeout:15000}).then(()=>true).catch(()=>false);
  const bounds=await page.evaluate(()=>{const nav=document.querySelector("nav").getBoundingClientRect(), map=document.querySelector("main[data-palette]").getBoundingClientRect();return {navRight:nav.right,mapLeft:map.left};});
  assert(bounds.mapLeft>=bounds.navRight,"map fixed positioning covers app navigation");
  await page.screenshot({path:join(shots,"visualizer-demo-1440.png"),fullPage:true});
  record("375/768/1280/1440 layouts and fixture wrapper preserve navigation");
  assert.deepEqual(consoleErrors,[],"browser page errors");
  await writeFile(join(evidence,"result.json"),JSON.stringify({ok:true,checks,first,second,cancelled:long,consoleErrors,shots,temp,mapIdle,mode:process.env.KAMI_E2E_DEV?"dev":"production"},null,2));
  console.log("E2E complete: "+checks.length+" checks");
}catch(e){
  if(browser){const pages=browser.contexts().flatMap(c=>c.pages());if(pages[0])await pages[0].screenshot({path:join(evidence,"failure.png"),fullPage:true}).catch(()=>{});}
  await writeFile(join(evidence,"result.json"),JSON.stringify({ok:false,checks,error:String(e),consoleErrors,temp},null,2));
  throw e;
}finally{await browser?.close();for(const child of [...children])await stop(child);}
