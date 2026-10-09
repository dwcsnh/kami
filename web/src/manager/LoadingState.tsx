import { Skeleton } from "@/components/ui/skeleton";
import s from "./manager.module.css";

export function LoadingState({ label = "Đang tải dữ liệu", variant = "table" }: { label?: string; variant?: "table" | "page" | "results" | "map" }) {
  return <div className={variant==="page"?s.page:s.loadingState} role="status" aria-label={label} aria-busy="true">
    <span className="sr-only">{label}</span>
    {variant==="page"&&<div className={s.loadingHeading}><Skeleton className="workspace-skeleton h-3 w-32"/><Skeleton className="workspace-skeleton h-9 w-72 max-w-full"/><Skeleton className="workspace-skeleton h-4 w-96 max-w-full"/></div>}
    {(variant==="page"||variant==="results")&&<div className={s.stats}>{[0,1,2].map(i=><div className={s.stat} key={i}><Skeleton className="workspace-skeleton h-4 w-32"/><Skeleton className="workspace-skeleton mt-4 h-9 w-20"/><Skeleton className="workspace-skeleton mt-3 h-3 w-48 max-w-full"/></div>)}</div>}
    {variant==="map"?<div className={s.loadingMap}><Skeleton className="workspace-skeleton h-full w-full"/><span className={s.loadingMapLabel}>Chuẩn bị không gian mô phỏng</span></div>:
      variant==="results"?<div className={s.card}><Skeleton className="workspace-skeleton h-5 w-48"/><Skeleton className="workspace-skeleton mt-6 h-64 w-full"/></div>:
      <div className={s.loadingTable} aria-hidden="true"><div className={s.loadingTableHead}>{[0,1,2,3].map(i=><Skeleton key={i} className="workspace-skeleton h-3 w-24 max-w-full"/>)}</div>{[0,1,2,3].map(i=><div key={i} className={s.loadingTableRow}><div><Skeleton className="workspace-skeleton h-4 w-36 max-w-full"/><Skeleton className="workspace-skeleton mt-3 h-3 w-24"/></div><Skeleton className="workspace-skeleton h-4 w-28 max-w-full"/><Skeleton className="workspace-skeleton h-6 w-20"/><Skeleton className="workspace-skeleton h-9 w-28 max-w-full"/></div>)}</div>}
  </div>;
}

export function LoadingValue({ label }: { label: string }) {
  return <span role="status" aria-label={"Đang tải "+label} className={s.loadingValue}><Skeleton className="workspace-skeleton h-9 w-20"/><span className="sr-only">Đang tải {label}</span></span>;
}
