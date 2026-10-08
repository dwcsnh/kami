// Small inline icon set (24 × 24, stroke = currentColor).
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 18, children, ...rest }: P & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>
      {children}
    </svg>
  );
}

export const IconPlay = (p: P) => <Svg {...p}><path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none" /></Svg>;
export const IconPause = (p: P) => (
  <Svg {...p}><rect x="6" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" />
    <rect x="14" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" /></Svg>
);
export const IconBack = (p: P) => <Svg {...p}><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" /></Svg>;
export const IconForward = (p: P) => <Svg {...p}><path d="M13 17l5-5-5-5M6 17l5-5-5-5" /></Svg>;
export const IconFit = (p: P) => (
  <Svg {...p}><path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4" /></Svg>
);
export const IconCube = (p: P) => (
  <Svg {...p}><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" /></Svg>
);
export const IconSquare = (p: P) => <Svg {...p}><rect x="4" y="4" width="16" height="16" rx="2" /></Svg>;
export const IconChevronRight = (p: P) => <Svg {...p}><path d="M9 6l6 6-6 6" /></Svg>;
export const IconChevronLeft = (p: P) => <Svg {...p}><path d="M15 6l-6 6 6 6" /></Svg>;
export const IconClose = (p: P) => <Svg {...p}><path d="M6 6l12 12M18 6L6 18" /></Svg>;
export const IconExpand = (p: P) => (
  <Svg {...p}><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></Svg>
);
export const IconCrosshair = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="7" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /></Svg>
);
export const IconChart = (p: P) => <Svg {...p}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></Svg>;
export const IconEye = (p: P) => (
  <Svg {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></Svg>
);
export const IconEyeOff = (p: P) => (
  <Svg {...p}><path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2" /></Svg>
);
export const IconPlus = (p: P) => <Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>;
export const IconMinus = (p: P) => <Svg {...p}><path d="M5 12h14" /></Svg>;
export const IconCompass = (p: P) => (
  <Svg {...p}><path d="M12 3l3.5 9h-7z" fill="#C92A2A" stroke="#C92A2A" /><path d="M12 21l-3.5-9h7z" /></Svg>
);
