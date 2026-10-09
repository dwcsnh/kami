"use client";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Empty, PageTitle } from "./components";
import RunResults from "./RunResults";
import s from "./manager.module.css";
import { LoadingState } from "./LoadingState";
const Visualizer=dynamic(()=>import("@/panels/Visualizer"),{ssr:false,loading:()=> <div className={s.visualizerLoading}><LoadingState variant="map" label="Đang tải bản đồ mô phỏng"/></div>});
export default function VisualizerPage(){
  const params=useSearchParams(),raw=params.get("run"),id=raw?Number(raw):null;
  if(raw)return <main className={s.page}><PageTitle eyebrow="THEO DÕI MÔ PHỎNG" title={"Thông tin run #"+raw} description="Trạng thái và metric được đọc từ backend."/>
    <p className={s.notice}>Bản đồ xe live và phát lại run qua API chưa được hỗ trợ ở giai đoạn này. <Link href="/visualizer">Mở bản đồ demo riêng →</Link></p>
    {Number.isSafeInteger(id)&&id!>0?<RunResults runId={id!}/>:<Empty>Run ID không hợp lệ.</Empty>}
  </main>;
  return <div className={s.visualizer}><div className={s.demoLabel}>DEMO FIXTURE · không phải run trong database</div><Visualizer/></div>;
}
