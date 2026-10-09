"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/ui";
import { Chart, axisStyle, chartBase } from "@/panels/Chart";
import { api } from "./api";
import { Empty, Errors, moment, Overview, Status } from "./components";
import { download, summaryCsv, timeseriesCsv } from "./csv";
import { formatMetric, metricKeys, metricLabel, metricUnit } from "./metricFormat";
import { useRuns } from "./RunProvider";
import { visibleMetric } from "./runState";
import { secondsToTime } from "./scenarioDraft";
import type { MetricRow, RunDetail } from "./types";
import s from "./manager.module.css";
import { Dropdown } from "./Dropdown";
import { LoadingState } from "./LoadingState";
export default function RunResults({runId}:{runId:number}) {
  const monitor=useRuns();
  const status=monitor.runs.find(r=>r.id===runId)?.status;
  const [result,setResult]=useState<{id:number;detail:RunDetail;summary:Record<string,number|null>;rows:MetricRow[]}|null>(null);
  const [error,setError]=useState<unknown>(null),[retry,setRetry]=useState(0),[metric,setMetric]=useState("rider.wait_mean"),[busy,setBusy]=useState(true);
  useEffect(()=>{
    let disposed=false;const abort=new AbortController();setError(null);setBusy(true);
    api.detail(runId,abort.signal).then(async detail=>{
      const data=detail.status==="succeeded"?await Promise.all([api.summary(runId,abort.signal),api.timeseries(runId,abort.signal)]):[{summary:{}},{rows:[]}];
      if(!disposed)setResult({id:runId,detail,summary:data[0].summary as Record<string,number|null>,rows:data[1].rows as MetricRow[]});
    }).catch(e=>{if(!disposed)setError(e);}).finally(()=>{if(!disposed)setBusy(false);});
    return()=>{disposed=true;abort.abort();};
  },[runId,status,retry]);
  const current=result?.id===runId?result:null;
  const detail=monitor.active?.id===runId?monitor.active:current?.detail;
  const live=monitor.live.runId===runId?monitor.live:null;
  const rows=detail?.status==="running"?(live?.rows??[]):current?.rows??[];
  const keys=useMemo(()=>metricKeys(rows),[rows]);
  const chosen=keys.includes(metric)?metric:keys[0]??"";
  const option=useMemo(()=>({
    ...chartBase,grid:{left:65,right:25,top:60,bottom:35},
    xAxis:{type:"value",...axisStyle,axisLabel:{...axisStyle.axisLabel,formatter:(v:number)=>secondsToTime(v)}},
    yAxis:{type:"value",...axisStyle,name:metricUnit(chosen)},
    tooltip:{...chartBase.tooltip,valueFormatter:(v:unknown)=>formatMetric(typeof v==="number"?v:null)},
    series:[{name:metricLabel(chosen),type:"line",symbol:"none",connectNulls:false,color:"#077C79",data:rows.map(r=>[r.t,r[chosen]??null])}],
  }),[rows,chosen]);
  async function cancel(){setBusy(true);setError(null);try{await api.cancel(runId);await monitor.refresh();setRetry(n=>n+1);}catch(e){setError(e);}finally{setBusy(false);}}
  const complete=detail?.status==="succeeded"&&current?.detail.status==="succeeded";
  return <section aria-label={"Kết quả run "+runId}>
    <Errors error={error}/>
    {!detail?(busy?<LoadingState variant="results" label={"Đang đọc kết quả run "+runId}/>:<Button onClick={()=>setRetry(n=>n+1)}>Thử tải lại run #{runId}</Button>):<>
      <div className={s.card}><div className={s.headingRow}><div><h2>Run #{runId} · {detail.name}</h2><p className={s.muted}>{detail.run_spec.scenario.name} · Seed {detail.seed??"—"} · {moment(detail.created_at)}</p></div><Status value={detail.status}/></div>
        <div className={s.actions} style={{marginTop:18}}>
          <Link href={"/visualizer?run="+runId}>Mở thông tin run →</Link>
          {detail.managed&&(detail.status==="queued"||detail.status==="running")&&<Button disabled={busy||!monitor.online} onClick={()=>void cancel()}>Huỷ run #{runId}</Button>}
          <Button size="sm" onClick={()=>setRetry(n=>n+1)} disabled={busy}>Làm mới kết quả</Button>
          <Button size="sm" disabled={!complete} onClick={()=>download("run-"+runId+"-summary.csv",summaryCsv(current!.summary))}>CSV tổng hợp</Button>
          <Button size="sm" disabled={!complete} onClick={()=>download("run-"+runId+"-timeseries.csv",timeseriesCsv(current!.rows))}>CSV chuỗi thời gian</Button>
        </div>
        {detail.error&&<p className={s.error}>{detail.error_code??"Lỗi mô phỏng"}: {detail.error}</p>}
        {detail.status!=="succeeded"&&detail.status!=="running"&&<p className={s.notice}>Kết quả hoàn chỉnh chỉ có khi run hoàn thành thành công.</p>}
      </div>
      {detail.status==="running"&&<p className={s.notice}>Metric live tạm thời · tối đa 2.000 hàng gần nhất.{live?.gap?" Có khoảng dữ liệu bị mất; sau khi run hoàn thành sẽ tải lại kết quả đầy đủ từ database.":""}{live?.trimmed?" Đang hiển thị cửa sổ 2.000 hàng gần nhất.":""}</p>}
      {busy&&detail&&<LoadingState variant="results" label="Đang cập nhật kết quả"/>}
      {complete&&!busy&&<Overview items={["platform.trips","rider.wait_mean","platform.gmv"].map((k,i)=>({label:metricLabel(k),value:<>{formatMetric(current!.summary[k])}<small>{metricUnit(k)}</small></>,hint:"Kết quả đã lưu · "+k,icon:(["car","scenario","chart"] as const)[i]}))}/>}
      {complete&&!busy&&current?.summary["shared.planned_pairs"]!==undefined&&<div className={s.card}><h2>Shared ride V1</h2><p className={s.muted}>Cước Shared = 70% cước đi riêng từng khách. Cặp đã tạo khác với cặp thực sự có hai khách trên xe; số liệu vi phạm phản ánh vận hành thực tế.</p><div className={s.tableWrap}><table className={s.table}><thead><tr><th>Lựa chọn</th><th>Đã đặt</th><th>Hoàn thành</th><th>Hủy</th><th>Chờ P95 (phút)</th><th>GMV (VND)</th></tr></thead><tbody>{["shared_only","exclusive_only"].map(pref=><tr key={pref}><td>{pref==="shared_only"?"Shared Only":"Exclusive Only"}</td>{["booked","served","cancelled","wait_p95","gmv"].map(k=><td key={k}>{formatMetric(current.summary[`shared.${pref}.${k}`])}</td>)}</tr>)}</tbody></table></div><p>Cặp đã tạo: {formatMetric(current.summary["shared.planned_pairs"])} · Có đi chung: {formatMetric(current.summary["shared.actual_pairs"])}</p></div>}
      {!busy&&(complete||detail.status==="running")&&<div className={s.card}><div className={s.headingRow}><h2>Diễn biến theo thời gian</h2>{keys.length>0&&<Dropdown className={s.select+" "+s.metricSelect} aria-label="Metric biểu đồ" value={chosen} onValueChange={value=>setMetric(value)}>{keys.map(k=><option key={k} value={k}>{metricLabel(k)} {metricUnit(k)&&"("+metricUnit(k)+")"}</option>)}</Dropdown>}</div>
        {rows.length?<><Chart option={option} height={300} ariaLabel={"Biểu đồ "+chosen}/><p className={s.muted}>Nguồn: {complete?"database":"SSE"} · {rows.length} hàng · {secondsToTime(rows[0].t)} – {secondsToTime(rows[rows.length-1].t)}</p></>:<Empty>Chưa có hàng metric. Dữ liệu xuất hiện theo nhịp lấy mẫu của kịch bản.</Empty>}
      </div>}
      {complete&&!busy&&<div className={s.tableWrap}><table className={s.table}><caption style={{textAlign:"left",padding:20,fontWeight:600}}>Chỉ số tổng hợp · dữ liệu đã lưu</caption><thead><tr><th>Chỉ số</th><th>Giá trị</th><th>Đơn vị</th></tr></thead><tbody>{Object.entries(current!.summary).filter(([k])=>visibleMetric(k)).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=><tr key={k} data-metric={k}><td>{metricLabel(k)}{metricLabel(k)!==k&&<small className={s.metricName}>{k}</small>}</td><td data-value={v??""}>{formatMetric(v)}</td><td>{metricUnit(k)}</td></tr>)}</tbody></table></div>}
    </>}
  </section>;
}
