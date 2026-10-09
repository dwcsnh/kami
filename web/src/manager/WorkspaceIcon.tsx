import type { SVGProps } from "react";
export type WorkspaceIconName = "scenario" | "car" | "chart" | "map" | "leaf" | "search";
const paths: Record<WorkspaceIconName, React.ReactNode> = {
  scenario: <><rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h5M8 16h3"/></>,
  car: <><path d="m5 7 2-4h10l2 4 2 3v8H3v-8zM3 10h18M7 14h1M16 14h1M5 18v3M19 18v3"/></>,
  chart: <><path d="M4 3v17h17M8 16v-5M13 16V7M18 16v-8"/></>,
  map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15"/></>,
  leaf: <><path d="M20 3c-9-1-16 3-16 10a7 7 0 0 0 7 7c7 0 10-8 9-17ZM4 21 15 10"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
};
export function WorkspaceIcon({ name, ...props }: SVGProps<SVGSVGElement> & { name: WorkspaceIconName }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>{paths[name]}</svg>;
}
