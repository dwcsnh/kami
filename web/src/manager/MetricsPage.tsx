"use client";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/ui";
import { api } from "./api";
import { Empty, Errors, Field, PageTitle, Status } from "./components";
import { comparisonCsv, download } from "./csv";
import { formatMetric, metricLabel, metricUnit, verdictLabel, warnings } from "./metricFormat";
import { useRuns } from "./RunProvider";
import RunResults from "./RunResults";
import { statusLabels, type Comparison } from "./types";
import s from "./manager.module.css";
import { LoadingState } from "./LoadingState";
import { Dropdown } from "./Dropdown";
export default function MetricsPage() {
  const params=useSearchParams(),router=useRouter(),monitor=useRuns();
  const raw=params.get("run"),runId=raw?Number(raw):null;
  const [mode,setMode]=useState<"single"|"compare">(params.has("ids")?"compare":"single");
  const [ids,setIds]=useState<number[]>(()=> (params.get("ids")??"").split(",").map(Number).filter(n=>Number.isSafeInteger(n)&&n>0));
  const [comparison,setComparison]=useState<Comparison|null>(null),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false);
  const version=useRef(0);
  const succeeded=monitor.runs.filter(r=>r.status==="succeeded").sort((a,b)=>b.id-a.id);
  useEffect(()=>()=>{version.current++;},[]);
  function select(next:number[]){version.current++;setIds(next);setComparison(null);setError(null);setBusy(false);}
  async function compare(){
    const v=++version.current;setBusy(true);setError(null);setComparison(null);
    try{const result=await api.compare(ids);if(v===version.current)setComparison(result);}
    catch(e){if(v===version.current)setError(e);}finally{if(v===version.current)setBusy(false);}
  }
  return <main className={s.page}><PageTitle eyebrow="PHÂN TÍCH HIỆU QUẢ" title="Kết quả & so sánh" description="Theo dõi chỉ số vận hành và tìm cấu hình phù hợp qua từng lần thử nghiệm."/>
    <div className={s.toolbar}><div className={s.tabs} role="tablist" aria-label="Chế độ metric"><button role="tab" aria-selected={mode==="single"} onClick={()=>setMode("single")}>Một lần chạy</button><button role="tab" aria-selected={mode==="compare"} onClick={()=>setMode("compare")}>So sánh các run</button></div><Button size="sm" onClick={()=>void monitor.refresh()}>Làm mới danh sách</Button></div>
    {mode==="single"?<>
      <div style={{maxWidth:600,marginBottom:24}}><Field label="Chọn run"><Dropdown disabled={!monitor.ready||!monitor.online} value={runId??""} onValueChange={value=>router.push(value?"/metrics?run="+value:"/metrics")}><option value="">Chọn một lần chạy</option>{[...monitor.runs].reverse().map(r=><option value={r.id} key={r.id}>#{r.id} · {r.name} · {statusLabels[r.status]}</option>)}</Dropdown></Field></div>
      {raw&&(!Number.isSafeInteger(runId)||runId!<=0)?<Empty>Run ID không hợp lệ.</Empty>:runId?<RunResults key={runId} runId={runId}/>:!monitor.ready?<LoadingState variant="results" label="Đang tải danh sách lần chạy"/>:<Empty>Chọn một run để xem kết quả tổng hợp và biểu đồ theo thời gian.</Empty>}
    </>:<>
      <div className={s.card}><h2>Chọn baseline và các run so sánh</h2><p className={s.muted}>Run đầu tiên là baseline. Chỉ so sánh các run đã hoàn thành thành công.</p>
        <div style={{maxWidth:600,marginTop:18}}><Field label="Baseline"><Dropdown disabled={!monitor.ready||!monitor.online} value={ids[0]??""} onValueChange={value=>select(value?[Number(value),...ids.slice(1).filter(i=>i!==Number(value))]:[])}><option value="">Chọn baseline</option>{succeeded.map(r=><option key={r.id} value={r.id}>#{r.id} · {r.name}</option>)}</Dropdown></Field></div>
        <div className={s.checkList}>{succeeded.filter(r=>r.id!==ids[0]).map(r=><label className={s.check} key={r.id}><input type="checkbox" disabled={!ids[0]||(!ids.includes(r.id)&&ids.length>=20)} checked={ids.slice(1).includes(r.id)} onChange={e=>select(e.target.checked?[...ids,r.id]:ids.filter(i=>i!==r.id))}/>#{r.id} · {r.name}</label>)}</div>
        <div className={s.actions} style={{marginTop:20}}><Button variant="primary" disabled={busy||ids.length<2||!monitor.online} onClick={()=>void compare()}>{busy?"Đang so sánh…":"So sánh"}</Button><Button disabled={!comparison} onClick={()=>comparison&&download("comparison-"+ids.join("-")+".csv",comparisonCsv(comparison))}>CSV so sánh</Button></div>
      </div><Errors error={error}/>
      {busy&&<LoadingState variant="results" label="Đang so sánh các lần chạy"/>}
      {comparison?.comparisons.map(c=><section key={c.run_id} className={s.history}><div className={s.headingRow}><h2>Run #{c.run_id} so với baseline #{comparison.baseline_id}</h2><Status value="succeeded"/></div>
        {c.warnings.length>0&&<div className={s.notice} role="status"><strong>Lưu ý khi diễn giải kết quả</strong><ul>{c.warnings.map(w=><li key={w}>{warnings[w]??w}</li>)}</ul></div>}
        <div className={s.tableWrap}><table className={s.table}><thead><tr><th>Chỉ số</th><th>Mốc đối chiếu</th><th>Lần chạy so sánh</th><th>Chênh lệch</th><th>Chênh lệch %</th><th>Đánh giá</th></tr></thead><tbody>{c.metrics.map(m=><tr key={m.metric} data-compare-metric={m.metric}><td className={s.metricName}>{metricLabel(m.metric)}<small>{metricUnit(m.metric)}</small></td><td>{formatMetric(m.baseline)}</td><td>{formatMetric(m.candidate)}</td><td data-delta={m.delta??""}>{formatMetric(m.delta)}</td><td>{formatMetric(m.delta_percent)}{m.delta_percent!=null?"%":""}</td><td data-verdict={m.verdict??""}>{m.verdict?verdictLabel[m.verdict]:"Chẩn đoán / chưa đủ số liệu"}</td></tr>)}</tbody></table></div>
      </section>)}
      {!monitor.ready?<LoadingState label="Đang tải các lần chạy"/>:!succeeded.length&&<Empty>Chưa có run thành công để so sánh.</Empty>}
    </>}
    <p className={s.notice}>Phân rã theo zone, fleet, loại xe và sản phẩm sẽ có khi backend cung cấp dữ liệu tương ứng. So sánh hiện tại không phải kiểm định thống kê nhiều seed.</p>
  </main>;
}
