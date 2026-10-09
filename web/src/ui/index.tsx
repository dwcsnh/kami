// kami 0.2 base components (sprint 03, S03-4) — reused by the Simulation manager (sprint 09).
"use client";

import { type ButtonHTMLAttributes, type KeyboardEvent, type PointerEvent, type ReactNode, useCallback, useRef, useId } from "react";
import { Switch } from "@/components/ui/switch";
import s from "./ui.module.css";

const cx = (...c: (string | false | undefined | null)[]) => c.filter(Boolean).join(" ");

// ---------------------------------------------------------------------------- Panel
export function Panel({ title, actions, children, className, bodyClassName, ...rest }: {
  title?: ReactNode; actions?: ReactNode; children?: ReactNode; className?: string; bodyClassName?: string;
} & Omit<React.HTMLAttributes<HTMLElement>, "title">) {
  return (
    <section className={cx(s.panel, className)} {...rest}>
      {(title || actions) && (
        <header className={s.panelHeader}>
          {typeof title === "string" ? <h2 className={s.panelTitle}>{title}</h2> : title}
          {actions}
        </header>
      )}
      <div className={cx(s.panelBody, bodyClassName)}>{children}</div>
    </section>
  );
}

// ---------------------------------------------------------------------------- Button
export function Button({ variant = "secondary", size = "md", className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost"; size?: "sm" | "md";
}) {
  return <button type="button" className={cx(s.button, s[variant], size === "sm" && s.small, className)} {...rest} />;
}

export function IconButton({ label, variant = "default", round, pressed, tooltip = true, tooltipSide = "top", className,
  children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string; variant?: "default" | "primary" | "bare"; round?: boolean; pressed?: boolean; tooltip?: boolean;
  tooltipSide?: "top" | "right";
}) {
  const btn = (
    <button type="button" aria-label={label} aria-pressed={pressed}
      className={cx(s.iconButton, variant === "primary" && s.iconButtonPrimary, variant === "bare" && s.iconButtonBare,
        round && s.iconButtonRound, className)} {...rest}>
      {children}
    </button>
  );
  return tooltip ? <Tooltip text={label} side={tooltipSide}>{btn}</Tooltip> : btn;
}

// ---------------------------------------------------------------------------- Tooltip
export function Tooltip({ text, side = "top", children }: { text: string; side?: "top" | "right"; children: ReactNode }) {
  return (
    <span className={cx(s.tooltipWrap, side === "right" && s.tooltipRight)}>
      {children}
      <span role="tooltip" className={s.tooltip}>{text}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------- Toggle
export function Toggle({ checked, onChange, label, id, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; id?: string; disabled?: boolean }) {
  const generatedId=useId(),controlId=id??generatedId;
  return <div className={s.switchRow}><Switch id={controlId} checked={checked} onCheckedChange={onChange} disabled={disabled} className={s.switchControl}/><label htmlFor={controlId}>{label}</label></div>;
}

// ---------------------------------------------------------------------------- Segmented
export function Segmented<T extends string | number>({ value, options, onChange, size = "md", label }: {
  value: T; options: { value: T; label: ReactNode; title?: string }[]; onChange: (v: T) => void; size?: "sm" | "md"; label: string;
}) {
  const onKey = (e: KeyboardEvent) => {
    const i = options.findIndex((o) => o.value === value);
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      e.stopPropagation();
      const j = (i + (e.key === "ArrowRight" ? 1 : options.length - 1)) % options.length;
      onChange(options[j].value);
    }
  };
  return (
    <div role="radiogroup" aria-label={label} className={cx(s.segmented, size === "sm" && s.segmentedSmall)} onKeyDown={onKey}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" role="radio" aria-checked={o.value === value} title={o.title}
          tabIndex={o.value === value ? 0 : -1} className={s.segOption} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------- KpiCard
export function KpiCard({ label, value, unit, hint, accent }: {
  label: string; value: ReactNode; unit?: string; hint?: ReactNode; accent?: string;
}) {
  return (
    <div className={s.kpi}>
      {accent && <span className={s.kpiAccent} style={{ background: accent }} />}
      <span className={s.kpiLabel}>{label}</span>
      <span className={s.kpiValue}>{value}{unit && <span className={s.kpiUnit}>{unit}</span>}</span>
      {hint && <span className={s.kpiHint}>{hint}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------- Timeline
export function Timeline({ value, min, max, onChange, ticks = [], label, step = 60, format }: {
  value: number; min: number; max: number; onChange: (v: number) => void; ticks?: { value: number; label: string }[];
  label: string; step?: number; format?: (v: number) => string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const span = Math.max(max - min, 1e-9);
  const frac = Math.min(1, Math.max(0, (value - min) / span));
  const fromEvent = useCallback((e: PointerEvent) => {
    const r = ref.current!.getBoundingClientRect();
    return min + Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * span;
  }, [min, span]);
  return (
    <div ref={ref} className={s.timeline} role="slider" tabIndex={0} aria-label={label} aria-valuemin={min}
      aria-valuemax={max} aria-valuenow={Math.round(value)} aria-valuetext={format?.(value)}
      onPointerDown={(e) => { ref.current!.setPointerCapture(e.pointerId); onChange(fromEvent(e)); }}
      onPointerMove={(e) => { if (ref.current!.hasPointerCapture(e.pointerId)) onChange(fromEvent(e)); }}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          e.stopPropagation();
          onChange(Math.min(max, Math.max(min, value + (e.key === "ArrowRight" ? step : -step))));
        } else if (e.key === "Home") onChange(min);
        else if (e.key === "End") onChange(max);
      }}>
      <div className={s.timelineTrack}><div className={s.timelineFill} style={{ width: `${frac * 100}%` }} /></div>
      <div className={s.timelineThumb} style={{ left: `${frac * 100}%` }} />
      {ticks.map((t) => (
        <span key={t.value} className={s.tick} style={{ left: `${((t.value - min) / span) * 100}%` }}>{t.label}</span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------- Legend item
export function LegendChip({ color, label, count, on, onToggle, emphasis }: {
  color: string; label: string; count?: number | string; on: boolean; onToggle: () => void; emphasis?: boolean;
}) {
  return (
    <button type="button" className={s.chip} aria-pressed={on} onClick={onToggle}
      title={on ? `Ẩn “${label}”` : `Hiện “${label}”`}>
      <span className={s.swatch}>
        <span className={s.swatchLine} style={{ background: color, height: emphasis ? 5 : 4 }} />
        <span className={s.swatchDot} style={{ background: color }} />
      </span>
      <span className={s.chipLabel}>{label}</span>
      {count !== undefined && <span className={s.chipCount}>{count}</span>}
    </button>
  );
}

export function Badge({ color, children }: { color?: string; children: ReactNode }) {
  return (
    <span className={s.badge}>
      {color && <span className={s.badgeDot} style={{ background: color }} />}
      {children}
    </span>
  );
}
