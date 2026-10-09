"use client";
import { cloneElement, isValidElement, useEffect, useId, useRef, type ReactElement, type ReactNode } from "react";
import { Button } from "@/ui";
import { ApiError } from "./api";
import { statusLabels, type RunStatus } from "./types";
import s from "./manager.module.css";
import { WorkspaceIcon, type WorkspaceIconName } from "./WorkspaceIcon";
import { LoadingValue } from "./LoadingState";
import { FormModal } from "./FormModal";
export function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: ReactNode }) {
  return <header className={s.pageHeader}><div><p className={s.eyebrow}>{eyebrow ?? "SIMULATION MANAGER"}</p><h1>{title}</h1><p className={s.muted}>{description}</p></div>{action}</header>;
}
export function Errors({ error }: { error: unknown }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (error) ref.current?.focus(); }, [error]);
  if (!error) return null;
  const errors = error instanceof ApiError ? error.errors : [{ path: "", message: error instanceof Error ? error.message : String(error) }];
  return <div className={s.error} role="alert" tabIndex={-1} ref={ref}><strong>Chưa hoàn tất thao tác</strong><ul>{errors.map((e,i) => <li key={i}>{e.path && <code>{e.path}: </code>}{e.message}</li>)}</ul></div>;
}
export function Field({ label, children, hint, error, path }: { label: string; children: ReactNode; hint?: string; error?: unknown; path?: string }) {
  const id = useId();
  const messages = error instanceof ApiError ? error.errors.filter(e => e.path === path) : [];
  const description = [hint && id + "-hint", messages.length > 0 && id + "-error"].filter(Boolean).join(" ") || undefined;
  const control = isValidElement(children) ? cloneElement(children as ReactElement<{ id?: string; "aria-describedby"?: string; "aria-invalid"?: boolean }>, { id, "aria-describedby": description, "aria-invalid": messages.length > 0 || undefined }) : children;
  return <div className={s.field}><label htmlFor={id}>{label}</label>{control}{hint && <small id={id + "-hint"}>{hint}</small>}{messages.length > 0 && <small id={id + "-error"} className={s.danger}>{messages.map(e => e.message).join(" · ")}</small>}</div>;
}
export function Empty({ children }: { children: ReactNode }) { return <div className={s.empty}><span className={s.emptyIcon}><WorkspaceIcon name="scenario" /></span><div className={s.emptyText}>{children}</div></div>; }
export function Search({ value, onChange, label }: { value: string; onChange: (value: string) => void; label: string }) {
  return <label className={s.search}><WorkspaceIcon name="search" /><input type="search" aria-label={label} placeholder={label} value={value} onChange={e => onChange(e.target.value)} /></label>;
}
export function Overview({ items }: { items: { label: string; value: ReactNode; hint: string; icon: WorkspaceIconName; loading?: boolean }[] }) {
  return <section className={s.stats} aria-label="Tổng quan">{items.map(item => <div className={s.stat} key={item.label} aria-busy={item.loading||undefined}><div className={s.statLabel}><WorkspaceIcon name={item.icon} />{item.label}</div><strong>{item.loading?<LoadingValue label={item.label}/>:item.value}</strong><small>{item.hint}</small></div>)}</section>;
}
export function Status({ value }: { value: RunStatus }) { return <span className={s.status} data-status={value}>{statusLabels[value]}</span>; }
export function Confirm({ name, busy, onCancel, onConfirm }: { name: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <FormModal title={"Xoá “"+name+"”?"} description="Mục này sẽ không còn trong danh sách cấu hình đang dùng. Lịch sử run vẫn được giữ." busy={busy} onClose={onCancel} compact>
    <div className={s.actions}><Button disabled={busy} onClick={onCancel}>Giữ lại</Button><Button disabled={busy} onClick={onConfirm}>Xác nhận xoá</Button></div>
  </FormModal>;
}
export const numberValue = (s: string) => s === "" ? "" : Number(s);
export function moment(value: string | null | undefined) {
  return value ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : value + "Z")) : "—";
}
