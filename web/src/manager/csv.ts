import type { Comparison, MetricRow } from "./types";
import { visibleMetric } from "./runState";
export function csvCell(value:unknown):string {
  if(value==null)return "";
  let text=String(value);
  if(typeof value==="string"&&/^[\s]*[=+@-]/.test(text))text="'"+text;
  return /[",\r\n]/.test(text)?'"'+text.replaceAll('"','""')+'"':text;
}
export function csv(rows:unknown[][]):string { return "\uFEFF"+rows.map(r=>r.map(csvCell).join(",")).join("\r\n")+"\r\n"; }
export function summaryCsv(summary:Record<string,number|null>):string { return csv([["metric","value"],...Object.entries(summary).filter(([k])=>visibleMetric(k)).sort(([a],[b])=>a.localeCompare(b))]); }
export function timeseriesCsv(rows:MetricRow[]):string {
  const keys=[...new Set(rows.flatMap(r=>Object.keys(r)))].filter(k=>k!=="t"&&visibleMetric(k)).sort();
  return csv([["t",...keys],...rows.map(r=>[r.t,...keys.map(k=>r[k]??null)])]);
}
export function comparisonCsv(data:Comparison):string {
  return csv([["baseline_id","candidate_id","warnings","metric","baseline","candidate","delta","delta_percent","direction","verdict"],
    ...data.comparisons.flatMap(c=>c.metrics.filter(m=>visibleMetric(m.metric)).map(m=>[data.baseline_id,c.run_id,c.warnings.join(";"),m.metric,m.baseline,m.candidate,m.delta,m.delta_percent,m.direction,m.verdict]))]);
}
export function download(name:string,text:string) {
  const url=URL.createObjectURL(new Blob([text],{type:"text/csv;charset=utf-8"}));
  const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
