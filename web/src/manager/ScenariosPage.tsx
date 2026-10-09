"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/ui";
import { api } from "./api";
import { Confirm, Empty, Errors, moment, Overview, PageTitle, Search, Status } from "./components";
import { useRuns } from "./RunProvider";
import { newScenario } from "./scenarioDraft";
import ScenarioForm from "./ScenarioForm";
import { startQueued } from "./runState";
import { useEntities } from "./useEntities";
import type { Entity, Fleet, RunDetail, RunSpec } from "./types";
import s from "./manager.module.css";
import { FormModal } from "./FormModal";
import { LoadingState } from "./LoadingState";
export default function ScenariosPage() {
  const scenarios=useEntities<RunSpec>("scenarios"),fleets=useEntities<Fleet>("fleets");
  const monitor=useRuns();
  const [editor,setEditor]=useState<{id?:number;spec:RunSpec}|null>(null),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false);
  const [deleting,setDeleting]=useState<Entity<RunSpec>|null>(null),[history,setHistory]=useState<RunDetail[]>([]);
  const [queued,setQueued]=useState<Record<number,number>>({}),[message,setMessage]=useState("");
  const [search,setSearch]=useState(""),[historyLoading,setHistoryLoading]=useState(true);
  const filtered=scenarios.items.filter(e=>e.name.toLocaleLowerCase("vi").includes(search.trim().toLocaleLowerCase("vi")));
  useEffect(()=>{let cancelled=false;monitor.details(monitor.runs).then(d=>{if(!cancelled)setHistory(d);}).catch(e=>{if(!cancelled)setError(e);}).finally(()=>{if(!cancelled&&monitor.ready)setHistoryLoading(false);});return()=>{cancelled=true;};},[monitor.runs,monitor.details,monitor.ready]);
  const blockRun=busy||!monitor.ready||!monitor.online||!!monitor.active;
  async function save(spec:RunSpec) {
    setBusy(true);setError(null);
    try {await api.save("scenarios",spec,editor?.id);setEditor(null);setMessage("Đã lưu kịch bản vào database.");await scenarios.reload();}
    catch(e){setError(e);}finally{setBusy(false);}
  }
  async function start(id:number) {
    setBusy(true);setError(null);setMessage("");
    try {
      await startQueued(()=>api.queue(id),api.start,queued[id],runId=>setQueued(q=>({...q,[id]:runId})));
      setQueued(q=>{const next={...q};delete next[id];return next;});
      setMessage("Đã bắt đầu mô phỏng.");
    }catch(e){setError(e);}finally{await monitor.refresh();setBusy(false);}
  }
  async function cancel(id:number) {
    setBusy(true);setError(null);
    try{await api.cancel(id);setQueued(q=>Object.fromEntries(Object.entries(q).filter(([,v])=>v!==id)));setMessage("Đã cập nhật trạng thái run.");}
    catch(e){setError(e);}finally{await monitor.refresh();setBusy(false);}
  }
  async function remove() {
    if(!deleting)return;const id=deleting.id;setDeleting(null);setBusy(true);setError(null);
    try{await api.remove("scenarios",id);await scenarios.reload();}
    catch(e){setError(e);}finally{setBusy(false);}
  }
  return <main className={s.page}>
    <PageTitle eyebrow="THIẾT KẾ & THỬ NGHIỆM" title="Kịch bản mô phỏng" description="Thử nghiệm nhu cầu di chuyển, cấu hình đội xe và đánh giá hiệu quả vận hành." action={<Button variant="primary" onClick={()=>{setEditor({spec:newScenario()});setError(null);setMessage("");}}>+ Tạo kịch bản</Button>}/>
    <Overview items={[
      {label:"Kịch bản đã lưu",loading:scenarios.loading,value:scenarios.error?"—":scenarios.items.length,hint:"Sẵn sàng cho lần thử nghiệm tiếp theo",icon:"scenario"},
      {label:"Lần chạy hoàn thành",loading:!monitor.ready,value:!monitor.online?"—":monitor.runs.filter(r=>r.status==="succeeded").length,hint:"Kết quả có thể xem và so sánh",icon:"chart"},
      {label:"Đội xe cấu hình",loading:fleets.loading,value:fleets.error?"—":fleets.items.length,hint:"Chọn đội xe phù hợp cho mỗi kịch bản",icon:"car"},
    ]}/>
    <Errors error={editor?null:error||scenarios.error||fleets.error}/>{message&&<p className={s.success} role="status">{message}</p>}
    {scenarios.loading?<LoadingState label="Đang tải kịch bản"/>:!scenarios.items.length?<Empty>Chưa có kịch bản. <Link href="/fleets">Cấu hình đội xe</Link>, sau đó chọn “Tạo kịch bản” để bắt đầu thử nghiệm.</Empty>:
      <section><div className={s.toolbar}><Search label="Tìm kịch bản theo tên…" value={search} onChange={setSearch}/><span className={s.resultCount}>{filtered.length} / {scenarios.items.length} kịch bản</span></div>
      {!filtered.length?<Empty>Không tìm thấy kịch bản. Thử tên khác hoặc xoá nội dung tìm kiếm.</Empty>:<div className={s.tableWrap}><table className={s.table}><thead><tr><th>Kịch bản</th><th>Cấu hình</th><th>Lần chạy gần nhất</th><th>Thao tác</th></tr></thead><tbody>{filtered.map(e=>{
        const last=history.find(r=>r.scenario_id===e.id);
        return <tr key={e.id}><td><strong>{e.name}</strong><small>Mã kịch bản #{e.id}</small></td>
        <td>{e.spec.scenario.network?.kind==="road"?"Mạng đường thật":"Lưới mô phỏng"}<small>{e.spec.scenario.source.kind==="preset"?"Nhu cầu từ mẫu":e.spec.scenario.source.kind==="synthetic"?"Nhu cầu tổng hợp":e.spec.scenario.source.kind==="zonal"?"Nhu cầu theo vùng":e.spec.scenario.source.kind} · {(e.spec.fleets??[]).length} đội xe</small></td>
        <td>{last?<><Link href={"/metrics?run="+last.id}>#{last.id}</Link> <Status value={last.status}/></>:"Chưa chạy"}</td>
        <td><div className={s.actions}><Button size="sm" variant="primary" disabled={blockRun} aria-label={queued[e.id]?"Bắt đầu run #"+queued[e.id]:"Chạy "+e.name} onClick={()=>void start(e.id)}>{queued[e.id]?"Bắt đầu #"+queued[e.id]:"Chạy"}</Button><Button size="sm" disabled={busy} aria-label={"Sửa "+e.name} onClick={()=>{setEditor({id:e.id,spec:e.spec});setError(null);setMessage("");}}>Sửa</Button><Button size="sm" variant="ghost" className={s.danger} disabled={busy} aria-label={"Xoá "+e.name} onClick={()=>setDeleting(e)}>Xoá</Button></div>{queued[e.id]&&<small>Snapshot đã tạo: <Link href={"/visualizer?run="+queued[e.id]}>run #{queued[e.id]}</Link></small>}</td></tr>;
      })}</tbody></table></div>}</section>}
    <section className={s.history}><div className={s.headingRow}><h2>Lịch sử lần chạy</h2><Button size="sm" disabled={busy} onClick={()=>void monitor.refresh()}>Làm mới run</Button></div>
      {!monitor.ready||historyLoading?<LoadingState label="Đang tải lịch sử lần chạy"/>:!monitor.runs.length?<Empty>Chưa có lần chạy nào trong database.</Empty>:<div className={s.tableWrap}><table className={s.table}><thead><tr><th>Run</th><th>Kịch bản</th><th>Trạng thái</th><th>Thời điểm tạo</th><th>Thao tác</th></tr></thead><tbody>{history.map(r=><tr key={r.id}><td>#{r.id} · {r.name}</td><td>{r.run_spec.scenario.name}</td><td><Status value={r.status}/>{r.error&&<small className={s.danger}>{r.error_code??"Lỗi mô phỏng"}: {r.error.split("\n").slice(-1)[0]}</small>}</td><td>{moment(r.created_at)}</td><td><div className={s.actions}><Link href={"/visualizer?run="+r.id}>Mở run</Link><Link href={"/metrics?run="+r.id}>Metric</Link>{r.managed&&r.status==="queued"&&<Button size="sm" disabled={blockRun} onClick={()=>{setBusy(true);setError(null);api.start(r.id).catch(setError).finally(async()=>{await monitor.refresh();setBusy(false);});}}>Bắt đầu #{r.id}</Button>}{r.managed&&(r.status==="queued"||r.status==="running")&&<Button size="sm" disabled={busy||!monitor.online} onClick={()=>void cancel(r.id)}>Huỷ #{r.id}</Button>}</div></td></tr>)}</tbody></table></div>}
    </section>
    {editor&&<FormModal title={editor.id?"Chỉnh sửa kịch bản":"Tạo kịch bản mới"} description="Cấu hình nhu cầu di chuyển, bản đồ và đội xe cho lần thử nghiệm." busy={busy} onClose={()=>{setEditor(null);setError(null);}}>
      <Errors error={error||fleets.error}/>
      <ScenarioForm key={editor.id??"new"} base={editor.spec} fleets={fleets.items} busy={busy} error={error} onSave={v=>void save(v)} onCancel={()=>{setEditor(null);setError(null);}}/>
    </FormModal>}
    {deleting&&<Confirm name={deleting.name} busy={busy} onCancel={()=>setDeleting(null)} onConfirm={()=>void remove()}/>}
  </main>;
}
